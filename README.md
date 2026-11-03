# Retail cancellation case study

Open dist/index.html. The month selector defaults to the peak cancellation month. Product ranks are based on positive cancellation value and show at most ten stock codes per month. Fees, postage, manual entries and similar adjustments (the NON_PRODUCT set in build.py) stay in all totals but are shown on one separate line and left out of the ranking. Stock code is the grouping key after trimming whitespace and upper-casing. Display descriptions use the first label that is not blank after trimming. December 2011 is partial. Product cancellation amounts and sales are event-month figures and are not matched to the same original purchase.

Source: https://archive.ics.uci.edu/dataset/352/online-retail

Install pandas and openpyxl. Download the UCI Online Retail ZIP and extract Online Retail.xlsx. Run python build.py "/path/to/Online Retail.xlsx" to rebuild dist/data.js and rerun the reconciliation. SQL aggregates monetary amounts in units of 0.0001 GBP. SQL and pandas share the same normalized inputs, so their agreement checks the implementation, not the definitions. build.py therefore also recomputes monthly sales, orders and cancellations straight from the raw file and asserts they match. The workbook compares exported SQL and pandas totals. The dashboard adds a mutually exclusive source-row reconciliation and shows source invoice examples.

Original code is released under CC0 1.0. Source data retains its original terms.

## What I found

December had £205,124.67 in recorded cancellations. One entry for £168,469.60 made up 82.1% of that total. The same item appears on a December sale for exactly that amount, so the two entries could be an order and its reversal.

Set both entries aside and December shows £36,655.07 in cancellations and £470,323.08 in gross sales. November had £47,740.08 in cancellations. The data covers only part of December, so that comparison tells us about the amounts recorded in each period.

## What I’d do next

I’d ask the order team to check whether invoice C581484 reversed invoice 581483. That one entry accounts for most of December’s recorded cancellation value, so it’s the first place I’d look. If the team confirms a reversal, I’d show its impact separately in the monthly report. I’d then compare cancellation rates over equivalent periods before deciding whether there’s a wider problem.
