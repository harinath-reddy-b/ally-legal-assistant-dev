echo off

url=YOUR_SEARCH_SERVICE_URL
admin_key=YOUR_ADMIN_API_KEY

echo -----
echo Creating the instructions index...
curl -X PUT $url/indexes/legal-instructions?api-version=2024-07-01 -H "Content-Type: application/json" -H "api-key: $admin_key" -d @legal-instructions-index.json

echo -----
echo Creating the documents index...
curl -X PUT $url/indexes/legal-documents?api-version=2024-07-01 -H "Content-Type: application/json" -H "api-key: $admin_key" -d @legal-documents-index.json