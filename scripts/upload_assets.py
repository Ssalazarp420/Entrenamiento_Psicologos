from azure.storage.blob import BlobServiceClient
import os

connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
client = BlobServiceClient.from_connection_string(connection_string)
container = client.get_container_client("assets")

# Subir toda la carpeta /frontend/public/assets
assets_path = "./frontend/public/assets"
for root, dirs, files in os.walk(assets_path):
    for file in files:
        file_path = os.path.join(root, file)
        blob_name = file_path.replace(assets_path + "/", "")
        with open(file_path, "rb") as data:
            container.upload_blob(blob_name, data, overwrite=True)
            print(f"✅ Subido: {blob_name}")
