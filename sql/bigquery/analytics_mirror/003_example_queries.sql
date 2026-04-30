SELECT
  reference_date,
  ticker,
  AVG(close_price) AS avg_close_price,
  COUNT(*) AS observations
FROM `<project-id>.<native_dataset>.quotes`
WHERE reference_date BETWEEN DATE '2026-04-01' AND DATE '2026-04-30'
GROUP BY 1, 2
ORDER BY 1, 2;

SELECT
  market_type,
  COUNT(DISTINCT ticker) AS ticker_count,
  SUM(close_price) AS notional_proxy
FROM `<project-id>.<external_dataset>.quotes_ext`
WHERE year = '2026' AND month = '04'
GROUP BY 1
ORDER BY 2 DESC;

SELECT
  q.reference_date,
  q.ticker,
  q.close_price,
  i.asset_type,
  i.segment
FROM `<project-id>.<native_dataset>.quotes` q
LEFT JOIN `<project-id>.<external_dataset>.instruments_ext` i
  ON q.ticker = i.ticker
WHERE q.reference_date = DATE '2026-04-28';