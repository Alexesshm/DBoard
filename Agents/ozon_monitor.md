# Agent: Ozon Monitor

## Responsibility
Fetch sales and inventory data from Ozon Seller API.

## Endpoints to use
- `https://api-seller.ozon.ru/v1/report/products/create` (For stocks via report)
- `https://api-seller.ozon.ru/v2/analytics/data` (For sales data)

## Authentication
Requires `Client-Id` and `Api-Key` headers.

## Output Format
Data should be processed into a clean JSON format for the dashboard aggregator.

## Safety
- Use `OZON_CLIENT_ID` and `OZON_API_KEY` from environment.
- Respect rate limits.
