# Agent: WB Monitor

## Responsibility
Fetch sales and inventory data from Wildberries Seller API (Statistics category).

## Endpoints to use
- `https://statistics-api.wildberries.ru/api/v1/supplier/stocks?dateFrom={date}` (Stocks)
- `https://statistics-api.wildberries.ru/api/v1/supplier/sales?dateFrom={date}` (Sales)

## Output Format
Data should be processed into a clean JSON format for the dashboard aggregator.

## Safety
- Use `WB_API_TOKEN` from environment.
- Respect rate limits.
