"""Test POST file upload to FastAPI backend."""

import json
import urllib.request
from pathlib import Path

def test_upload():
    sample = Path(r"C:\Users\Mr.Chuong\Downloads\Hóa đơn mẫu\1C26TAP_00006732_0317333953.pdf")
    boundary = "----WebKitFormBoundaryTest12345"

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="files"; filename="{sample.name}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: application/pdf\r\n\r\n")
    body.extend(sample.read_bytes())
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "http://localhost:8000/api/v1/accounting/batches",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )

    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode("utf-8"))
    print(f"POST UPLOAD SUCCESSFUL! Status code: {res.status}")
    print(f"Batch ID: {data['batch_id']}")
    print(f"Extracted File: {data['items'][0]['file_name']}")
    print(f"Supplier: {data['items'][0]['extraction'].get('supplier_name')}")
    print(f"Total Amount: {data['items'][0]['extraction'].get('total_amount')} VND")

if __name__ == "__main__":
    test_upload()
