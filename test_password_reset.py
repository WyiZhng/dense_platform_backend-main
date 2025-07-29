"""
Test script for password reset functionality

This script tests the complete password reset workflow including:
1. Requesting a password reset token
2. Validating the reset token
3. Resetting the password
4. Verifying the new password works
"""

import requests
import json
from datetime import datetime


class PasswordResetTest:
    """Test class for password reset functionality"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_user = {
            "username": "test_reset_user",
            "password": "original_password_123",
            "type": 0  # Patient
        }
        self.new_password = "new_password_456"
        self.token = None
        self.reset_token = None
    
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
                print(f"✅ User registered successfully")
                return True
            else:
                print(f"❌ Registration failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Registration request failed: {response.status_code}")
            return False
    
    def logout_user(self):
        """Logout the user"""
        print("2. Logging out user...")
        
        if not self.token:
            print("✅ No token to logout")
            return True
        
        response = requests.post(
            f"{self.base_url}/api/logout",
            json={"token": self.token}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                print("✅ User logged out successfully")
                self.token = None
                return True
            else:
                print(f"❌ Logout failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Logout request failed: {response.status_code}")
            return False
    
    def request_password_reset(self):
        """Request a password reset token"""
        print("3. Requesting password reset token...")
        
        response = requests.post(
            f"{self.base_url}/api/auth/request-password-reset",
            json={"username": self.test_user["username"]}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                self.reset_token = data.get("reset_token")
                expires_at = data.get("expires_at")
                print(f"✅ Password reset token generated")
                print(f"   Token: {self.reset_token[:20]}...")
                print(f"   Expires at: {expires_at}")
                return True
            else:
                print(f"❌ Failed to request reset: {data.get('message')}")
                return False
        else:
            print(f"❌ Reset request failed: {response.status_code}")
            return False
    
    def validate_reset_token(self):
        """Validate the reset token"""
        print("4. Validating reset token...")
        
        response = requests.post(
            f"{self.base_url}/api/auth/validate-reset-token",
            json={"token": self.reset_token}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and data.get("valid"):
                user_id = data.get("user_id")
                expires_at = data.get("expires_at")
                print(f"✅ Reset token is valid")
                print(f"   User ID: {user_id}")
                print(f"   Expires at: {expires_at}")
                return True
            else:
                print(f"❌ Reset token is invalid: {data.get('message')}")
                return False
        else:
            print(f"❌ Token validation failed: {response.status_code}")
            return False
    
    def reset_password(self):
        """Reset the password using the token"""
        print("5. Resetting password...")
        
        response = requests.post(
            f"{self.base_url}/api/auth/reset-password",
            json={
                "token": self.reset_token,
                "new_password": self.new_password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                print("✅ Password reset successfully")
                return True
            else:
                print(f"❌ Password reset failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Password reset request failed: {response.status_code}")
            return False
    
    def test_old_password(self):
        """Test that old password no longer works"""
        print("6. Testing old password (should fail)...")
        
        response = requests.post(
            f"{self.base_url}/api/login",
            json={
                "username": self.test_user["username"],
                "password": self.test_user["password"]  # Old password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") != 0:
                print("✅ Old password correctly rejected")
                return True
            else:
                print("❌ Old password still works (should not happen)")
                return False
        else:
            print("✅ Old password correctly rejected (request failed)")
            return True
    
    def test_new_password(self):
        """Test that new password works"""
        print("7. Testing new password (should work)...")
        
        response = requests.post(
            f"{self.base_url}/api/login",
            json={
                "username": self.test_user["username"],
                "password": self.new_password  # New password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                self.token = data.get("token")
                print("✅ New password works correctly")
                return True
            else:
                print(f"❌ New password failed: {data.get('message')}")
                return False
        else:
            print(f"❌ New password login failed: {response.status_code}")
            return False
    
    def test_used_token(self):
        """Test that used reset token cannot be used again"""
        print("8. Testing used reset token (should fail)...")
        
        response = requests.post(
            f"{self.base_url}/api/auth/reset-password",
            json={
                "token": self.reset_token,
                "new_password": "another_password_789"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") != 0:
                print("✅ Used reset token correctly rejected")
                return True
            else:
                print("❌ Used reset token still works (should not happen)")
                return False
        else:
            print("✅ Used reset token correctly rejected (request failed)")
            return True
    
    def test_change_password(self):
        """Test changing password with current password"""
        print("9. Testing password change with current password...")
        
        another_new_password = "changed_password_789"
        
        response = requests.post(
            f"{self.base_url}/api/auth/change-password",
            json={
                "username": self.test_user["username"],
                "old_password": self.new_password,
                "new_password": another_new_password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                print("✅ Password changed successfully")
                
                # Test the changed password
                login_response = requests.post(
                    f"{self.base_url}/api/login",
                    json={
                        "username": self.test_user["username"],
                        "password": another_new_password
                    }
                )
                
                if login_response.status_code == 200:
                    login_data = login_response.json()
                    if login_data.get("code") == 0:
                        self.token = login_data.get("token")
                        print("✅ Changed password works correctly")
                        return True
                    else:
                        print(f"❌ Changed password doesn't work: {login_data.get('message')}")
                        return False
                else:
                    print(f"❌ Changed password login failed: {login_response.status_code}")
                    return False
            else:
                print(f"❌ Password change failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Password change request failed: {response.status_code}")
            return False
    
    def cleanup_test_user(self):
        """Clean up test user"""
        print("10. Cleaning up test user...")
        if self.token:
            requests.post(
                f"{self.base_url}/api/logout",
                json={"token": self.token}
            )
        print("✅ Test cleanup completed")
    
    def run_test(self):
        """Run the complete test"""
        print("=" * 60)
        print("PASSWORD RESET FUNCTIONALITY TEST")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print(f"Test started at: {datetime.now()}")
        print()
        
        try:
            # Test steps
            steps = [
                self.register_test_user,
                self.logout_user,
                self.request_password_reset,
                self.validate_reset_token,
                self.reset_password,
                self.test_old_password,
                self.test_new_password,
                self.test_used_token,
                self.test_change_password,
                self.cleanup_test_user
            ]
            
            for step in steps:
                if not step():
                    print()
                    print("=" * 60)
                    print("💥 TEST FAILED: One or more steps failed!")
                    print("=" * 60)
                    self.cleanup_test_user()
                    return False
                print()
            
            print("=" * 60)
            print("🎉 ALL TESTS PASSED: Password reset functionality works correctly!")
            print("=" * 60)
            return True
            
        except Exception as e:
            print(f"❌ Test failed with exception: {str(e)}")
            self.cleanup_test_user()
            return False


def main():
    """Main function to run the test"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test password reset functionality")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API server (default: http://localhost:8000)"
    )
    
    args = parser.parse_args()
    
    test = PasswordResetTest(args.url)
    success = test.run_test()
    
    exit(0 if success else 1)


if __name__ == "__main__":
    main()