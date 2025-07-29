"""
Test script to verify that user data is preserved after logout

This script tests the logout data preservation functionality to ensure
that user details, avatars, and other data remain intact after logout.
"""

import requests
import json
from datetime import datetime


class LogoutDataPreservationTest:
    """Test class for logout data preservation"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_user = {
            "username": "test_logout_user",
            "password": "test_password_123",
            "type": 0  # Patient
        }
        self.test_user_info = {
            "name": "Test User",
            "sex": 1,  # Male
            "birth": "1990-01-01",
            "phone": "1234567890",
            "email": "test@example.com",
            "address": "Test Address 123"
        }
        self.token = None
    
    def register_test_user(self):
        """Register a test user"""
        print("1. Registering test user...")
        
        response = requests.post(
            f"{self.base_url}/api/register",
            json=self.test_user
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                self.token = data.get("token")
                print(f"✅ User registered successfully. Token: {self.token[:20]}...")
                return True
            else:
                print(f"❌ Registration failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Registration request failed: {response.status_code}")
            return False
    
    def submit_user_info(self):
        """Submit user detailed information"""
        print("2. Submitting user detailed information...")
        
        response = requests.post(
            f"{self.base_url}/api/submitInfo",
            json={
                "token": self.token,
                "form": self.test_user_info
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                print("✅ User information submitted successfully")
                return True
            else:
                print(f"❌ Failed to submit user info: {data.get('message')}")
                return False
        else:
            print(f"❌ Submit info request failed: {response.status_code}")
            return False
    
    def get_user_info_before_logout(self):
        """Get user information before logout"""
        print("3. Getting user information before logout...")
        
        response = requests.post(
            f"{self.base_url}/api/info",
            json={"token": self.token}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                form_data = data.get("form", {})
                print("✅ User information retrieved before logout:")
                print(f"   Name: {form_data.get('name')}")
                print(f"   Email: {form_data.get('email')}")
                print(f"   Phone: {form_data.get('phone')}")
                return form_data
            else:
                print(f"❌ Failed to get user info: {data.get('message')}")
                return None
        else:
            print(f"❌ Get info request failed: {response.status_code}")
            return None
    
    def logout_user(self):
        """Logout the user"""
        print("4. Logging out user...")
        
        response = requests.post(
            f"{self.base_url}/api/logout",
            json={"token": self.token}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                print("✅ User logged out successfully")
                return True
            else:
                print(f"❌ Logout failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Logout request failed: {response.status_code}")
            return False
    
    def login_again(self):
        """Login again with the same credentials"""
        print("5. Logging in again...")
        
        response = requests.post(
            f"{self.base_url}/api/login",
            json={
                "username": self.test_user["username"],
                "password": self.test_user["password"]
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                self.token = data.get("token")
                print(f"✅ User logged in again successfully. New token: {self.token[:20]}...")
                return True
            else:
                print(f"❌ Login failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Login request failed: {response.status_code}")
            return False
    
    def get_user_info_after_login(self):
        """Get user information after logging in again"""
        print("6. Getting user information after logging in again...")
        
        response = requests.post(
            f"{self.base_url}/api/info",
            json={"token": self.token}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                form_data = data.get("form", {})
                print("✅ User information retrieved after login:")
                print(f"   Name: {form_data.get('name')}")
                print(f"   Email: {form_data.get('email')}")
                print(f"   Phone: {form_data.get('phone')}")
                return form_data
            else:
                print(f"❌ Failed to get user info: {data.get('message')}")
                return None
        else:
            print(f"❌ Get info request failed: {response.status_code}")
            return None
    
    def compare_data(self, before_data, after_data):
        """Compare data before and after logout"""
        print("7. Comparing data before and after logout...")
        
        if not before_data or not after_data:
            print("❌ Cannot compare data - missing data")
            return False
        
        # Compare key fields
        fields_to_compare = ["name", "email", "phone", "address"]
        all_match = True
        
        for field in fields_to_compare:
            before_value = before_data.get(field)
            after_value = after_data.get(field)
            
            if before_value == after_value:
                print(f"✅ {field}: {before_value} (preserved)")
            else:
                print(f"❌ {field}: {before_value} -> {after_value} (changed!)")
                all_match = False
        
        if all_match:
            print("✅ All user data preserved after logout!")
            return True
        else:
            print("❌ Some user data was lost after logout!")
            return False
    
    def cleanup_test_user(self):
        """Clean up test user (optional)"""
        print("8. Cleaning up test user...")
        # Note: In a real scenario, you might want to delete the test user
        # For now, we'll just log out
        if self.token:
            requests.post(
                f"{self.base_url}/api/logout",
                json={"token": self.token}
            )
        print("✅ Test cleanup completed")
    
    def run_test(self):
        """Run the complete test"""
        print("=" * 60)
        print("LOGOUT DATA PRESERVATION TEST")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print(f"Test started at: {datetime.now()}")
        print()
        
        try:
            # Step 1: Register user
            if not self.register_test_user():
                return False
            
            # Step 2: Submit user information
            if not self.submit_user_info():
                return False
            
            # Step 3: Get user info before logout
            before_data = self.get_user_info_before_logout()
            if not before_data:
                return False
            
            # Step 4: Logout
            if not self.logout_user():
                return False
            
            # Step 5: Login again
            if not self.login_again():
                return False
            
            # Step 6: Get user info after login
            after_data = self.get_user_info_after_login()
            if not after_data:
                return False
            
            # Step 7: Compare data
            success = self.compare_data(before_data, after_data)
            
            # Step 8: Cleanup
            self.cleanup_test_user()
            
            print()
            print("=" * 60)
            if success:
                print("🎉 TEST PASSED: User data is preserved after logout!")
            else:
                print("💥 TEST FAILED: User data was not preserved after logout!")
            print("=" * 60)
            
            return success
            
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            self.cleanup_test_user()
            return False


def main():
    """Main function to run the test"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test logout data preservation")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API server (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    test = LogoutDataPreservationTest(args.url)
    success = test.run_test()
    
    exit(0 if success else 1)


if __name__ == "__main__":
    main()