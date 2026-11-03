import json, sqlite3, sys
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parent
raw = pd.read_excel(sys.argv[1], dtype={'InvoiceNo': str, 'StockCode': str})

# Fees, postage, manual entries and similar adjustments. They stay in every total
# but are kept out of the product ranking.
NON_PRODUCT = {'POST', 'D', 'M', 'DOT', 'CRUK', 'AMAZONFEE', 'BANK CHARGES', 'S', 'B', 'C2', 'PADS', 'ADJUST', 'ADJUST2'}

raw['sku'] = raw.StockCode.str.strip().str.upper()
lines = pd.DataFrame(dict(invoice=raw.InvoiceNo, sku=raw.sku, qty=raw.Quantity,
    price=(raw.UnitPrice * 10000).round().astype('int64'), month=raw.InvoiceDate.dt.strftime('%Y-%m'),
    cancellation=raw.InvoiceNo.str.upper().str.startswith('C').astype(int)))
lines['amount'] = lines.qty * lines.price
rules = {'Nonpositive price': lines.price.le(0),
         'Included sales': lines.price.gt(0) & lines.qty.gt(0) & lines.cancellation.eq(0),
         'Included cancellations': lines.price.gt(0) & lines.qty.lt(0) & lines.cancellation.eq(1)}
rules['Other sign or prefix'] = ~pd.DataFrame(rules).any(axis=1)
assert pd.DataFrame(rules).sum(axis=1).eq(1).all()
audit = [dict(rule=name, rows=int(mask.sum()), signed_gbp=int(lines.loc[mask, 'amount'].sum()) / 10000) for name, mask in rules.items()]
assert sum(row['rows'] for row in audit) == len(raw)
sales = lines[rules['Included sales']]
cancel = lines[rules['Included cancellations']]
with sqlite3.connect(':memory:') as db:
    lines.to_sql('lines', db, index=False)
    monthly = pd.read_sql_query((root / 'retail.sql').read_text(), db)

# Check 1: pandas on the normalized table agrees with SQL.
for row in monthly.itertuples():
    s = sales[sales.month.eq(row.month)]
    c = cancel[cancel.month.eq(row.month)]
    assert (s.amount.sum(), s.invoice.nunique(), -c.amount.sum()) == (row.gross, row.orders, row.cancelled)

# Check 2: totals recomputed straight from the raw file, bypassing the normalized table and SQL.
rmonth = raw.InvoiceDate.dt.strftime('%Y-%m')
rcanc = raw.InvoiceNo.str.upper().str.startswith('C')
rval = raw.Quantity * raw.UnitPrice
ok = raw.UnitPrice.gt(0)
rsales = rval[ok & ~rcanc & raw.Quantity.gt(0)].groupby(rmonth[ok & ~rcanc & raw.Quantity.gt(0)]).sum()
rcan = (-rval[ok & rcanc & raw.Quantity.lt(0)]).groupby(rmonth[ok & rcanc & raw.Quantity.lt(0)]).sum()
rord = raw[ok & ~rcanc & raw.Quantity.gt(0)].groupby(rmonth).InvoiceNo.nunique()
for row in monthly.itertuples():
    assert abs(rsales.get(row.month, 0) - row.gross / 10000) < 0.01, row.month
    assert abs(rcan.get(row.month, 0) - row.cancelled / 10000) < 0.01, row.month
    assert rord.get(row.month, 0) == row.orders, row.month

# Labels: first label that is not blank after trimming.
desc = raw.assign(label=raw.Description.str.strip()).dropna(subset=['label'])
labels = desc[desc.label.ne('')].drop_duplicates('sku').set_index('sku').label

products = sales.groupby(['month', 'sku']).amount.sum().rename('sales').to_frame().join(
    (-cancel.groupby(['month', 'sku']).amount.sum()).rename('cancelled'), how='outer').fillna(0).reset_index()
assert int(products.cancelled.sum()) == int(monthly.cancelled.sum())
assert int(products.sales.sum()) == int(monthly.gross.sum())
products['label'] = products.sku.map(labels).fillna('')
is_adj = products.sku.isin(NON_PRODUCT)
adj = products[is_adj].groupby('month').cancelled.sum()
monthly['adjustment_cancelled'] = monthly.month.map(adj).fillna(0).astype('int64')
real = products[~is_adj]
assert int(real.cancelled.sum() + adj.sum()) == int(monthly.cancelled.sum())
ranked = real[real.cancelled.gt(0)].sort_values(['cancelled', 'sku'], ascending=[False, True]).groupby('month').head(10)

peak = monthly.loc[monthly.cancelled.idxmax(), 'month']
sku = ranked[ranked.month.eq(peak)].iloc[0].sku
trace = cancel[cancel.month.eq(peak) & cancel.sku.eq(sku)].sort_values('amount').head(5)
matching = sales[sales.month.eq(peak) & sales.sku.eq(sku) & sales.amount.isin(-trace.amount)].head(5)

# Sensitivity: largest single cancellation line in the peak month, and any equal and opposite
# sale for the same stock code in the same month. Both sides are removed so gross stays consistent.
big = cancel[cancel.month.eq(peak)].nsmallest(1, 'amount').iloc[0]
twin = sales[sales.month.eq(peak) & sales.sku.eq(big.sku) & sales.amount.eq(-big.amount)]
pk = monthly[monthly.month.eq(peak)].iloc[0]
sensitivity = dict(invoice=big.invoice, sku=big.sku, line=int(-big.amount),
    matched_invoice=(twin.iloc[0].invoice if len(twin) else None),
    cancelled=int(pk.cancelled), cancelled_excl=int(pk.cancelled + big.amount),
    gross=int(pk.gross), gross_excl=int(pk.gross - (twin.iloc[0].amount if len(twin) else 0)))

payload = dict(monthly=monthly.to_dict('records'), products=ranked.to_dict('records'), audit=audit,
    trace=pd.concat([trace, matching])[['invoice', 'sku', 'qty', 'price', 'amount']].to_dict('records'),
    peak=peak, sensitivity=sensitivity)
(root / 'dist' / 'data.js').write_text('const DATA = ' + json.dumps(payload, allow_nan=False, default=int) + ';\n')
print(peak, ranked[ranked.month.eq(peak)].head(4).to_string(index=False), audit, trace.to_string(index=False), sensitivity, sep='\n')
