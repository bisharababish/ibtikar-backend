#!/usr/bin/env python3
"""Generate a valid Fernet key for use in environment variables."""
from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key()
    print("=" * 60)
    print("Generated FERNET_KEY (copy this exactly):")
    print("=" * 60)
    print(key.decode())
    print("=" * 60)
    print(f"Key length: {len(key.decode())} characters")
    print("=" * 60)
    print("\nInstructions:")
    print("1. Copy the key above (between the === lines)")
    print("2. Go to Render dashboard → Environment tab")
    print("3. Find FERNET_KEY and paste the new key")
    print("4. Save and redeploy")




