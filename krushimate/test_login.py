import requests

# Test login with non-existent user
response = requests.post('http://127.0.0.1:5000/api/login', json={
    'username': 'test',
    'password': 'test'
})
print("Login test (non-existent user):")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Test registration
print("\n--- Testing Registration ---")
response = requests.post('http://127.0.0.1:5000/api/register', json={
    'first_name': 'Test',
    'last_name': 'User',
    'city': 'Mumbai',
    'contact': '1234567890',
    'email': 'test@example.com',
    'username': 'testuser',
    'password': 'password123',
    'confirm_password': 'password123'
})
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Test login again with new user
print("\n--- Testing Login with new user ---")
response = requests.post('http://127.0.0.1:5000/api/login', json={
    'username': 'testuser',
    'password': 'password123'
})
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

