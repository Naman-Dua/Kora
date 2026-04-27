
import requests
import pandas as pd
from datetime import datetime

# Set API endpoint and parameters
api_url = 'https://api.coingecko.com/api/v3/coins/markets'
params = {
'vs_currency': 'usd',
'ids': 'bitcoin,ethereum,litecoin', # Replace with desired cryptocurrencies
'order': 'market_cap_desc',
'per_page': 100,
'page': 1,
'sparkline': False
}

# Send GET request to API and retrieve data
response = requests.get(api_url, params=params)

# Check if request was successful
if response.status_code == 200:
# Parse JSON response into a pandas DataFrame
    data = pd.DataFrame(response.json())

# Save the price history to a CSV file for future reference
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    data.to_csv(f'crypto_prices_{timestamp}.csv', index=False)

    print('Crypto prices updated successfully!')
else:
    print(f'Error fetching crypto prices: {response.status_code}')
