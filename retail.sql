SELECT month,
 SUM(CASE WHEN cancellation=0 AND qty>0 THEN qty*price ELSE 0 END) AS gross,
 COUNT(DISTINCT CASE WHEN cancellation=0 AND qty>0 THEN invoice END) AS orders,
 SUM(CASE WHEN cancellation=1 AND qty<0 THEN -qty*price ELSE 0 END) AS cancelled
FROM lines WHERE price>0 GROUP BY month ORDER BY month;
