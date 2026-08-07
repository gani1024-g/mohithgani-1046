import qrcode

# Create a QR code with your data
img = qrcode.make("https://python.org")

# Save the QR code as an image file
with open("python_qr.png", "wb") as f:
    img.save(f)

print("QR Code generated successfully!")
