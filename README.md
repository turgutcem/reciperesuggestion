# Edamam API Data Exploration

This step of the project explores data retrieved from the Edamam Recipe Search API.

## Data Collection

The data is collected using the `requests` library in Python. The script makes GET requests to the Edamam API endpoint with specific parameters:

- `q`: The search query (e.g., "chicken").
- `app_id`: Your Edamam application ID.
- `app_key`: Your Edamam application key.
- `from`: The starting index for pagination.
- `to`: The ending index for pagination.

Additional parameters like `diet`, `health`, `cuisineType`, and `mealType` are used for filtering results based on user preferences.

## Data Source

The data is collected from the Edamam Recipe Search API. You can find more information about the API and how to obtain your application ID and key on the Edamam website. Replace the placeholders for `app_id` and `app_key` in the script with your actual credentials.

**Note**:

- Ensure you have the necessary libraries installed (`requests`, `json`, `pandas`, `json_normalize`).
- Replace the placeholder values for `app_id` and `app_key` with your actual Edamam API credentials.
- Execute the code step-by-step in a Google Colab or Jupyter Notebook environment to fetch and process the data.
