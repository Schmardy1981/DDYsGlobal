import requests
import sys
import json
from datetime import datetime

class DDYsComplianceAPITester:
    def __init__(self, base_url="https://kyc-flow-5.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tenant_id = None
        self.case_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

    def log_result(self, test_name, success, message="", response_data=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {test_name}: {message}")
        else:
            print(f"❌ {test_name}: {message}")
        
        self.results.append({
            "test_name": test_name,
            "success": success,
            "message": message,
            "response_data": response_data
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}" if not endpoint.startswith('/') else f"{self.base_url}{endpoint}"
        
        default_headers = {'Content-Type': 'application/json'}
        if self.token:
            default_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            default_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=default_headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.log_result(name, True, f"Status: {response.status_code}", response.json() if response.content else {})
                return True, response.json() if response.content else {}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_detail = response.json().get('detail', '')
                    error_msg += f" - {error_detail}"
                except:
                    pass
                self.log_result(name, False, error_msg)
                return False, {}

        except Exception as e:
            self.log_result(name, False, f"Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        success, response = self.run_test("Health Check", "GET", "health", 200)
        return success

    def test_seed_data(self):
        """Test seeding demo data"""
        success, response = self.run_test("Seed Demo Data", "POST", "seed", 200)
        if success and "tenant_id" in response:
            self.tenant_id = response["tenant_id"]
        return success

    def test_admin_login(self):
        """Test admin login"""
        login_data = {"email": "admin@ddys.com", "password": "Admin123!"}
        success, response = self.run_test("Admin Login", "POST", "auth/login", 200, login_data)
        
        if success and "token" in response:
            self.token = response["token"]
            return True
        elif success and response.get("requires_mfa"):
            # Handle MFA case
            mfa_data = {"mfa_token": response["mfa_token"], "code": "123456"}
            success, mfa_response = self.run_test("Admin MFA Verify", "POST", "auth/mfa/verify", 200, mfa_data)
            if success and "token" in mfa_response:
                self.token = mfa_response["token"]
                return True
        return False

    def test_maker_login(self):
        """Test maker login and store token separately"""
        login_data = {"email": "maker@ddys.com", "password": "Maker123!"}
        success, response = self.run_test("Maker Login", "POST", "auth/login", 200, login_data)
        return success and ("token" in response or response.get("requires_mfa"))

    def test_customer_login(self):
        """Test customer login flow"""
        login_data = {"email": "customer@example.com", "password": "Cust123!"}
        success, response = self.run_test("Customer Login", "POST", "auth/login", 200, login_data)
        return success

    def test_get_tenants(self):
        """Test getting tenants"""
        success, response = self.run_test("Get Tenants", "GET", "tenants", 200)
        if success and response and len(response) > 0:
            if not self.tenant_id:
                self.tenant_id = response[0]["id"]
        return success

    def test_get_cases(self):
        """Test getting cases"""
        success, response = self.run_test("Get Cases", "GET", "cases", 200)
        if success and response and len(response) > 0:
            self.case_id = response[0]["id"]
        return success

    def test_create_case(self):
        """Test creating a new case"""
        if not self.tenant_id:
            self.log_result("Create Case", False, "No tenant_id available")
            return False
            
        case_data = {
            "tenant_id": self.tenant_id,
            "case_type": "onboarding",
            "jurisdiction": "EU",
            "product_scope": "Corporate Banking"
        }
        success, response = self.run_test("Create Case", "POST", "cases", 200, case_data)
        if success and "id" in response:
            self.case_id = response["id"]
        return success

    def test_get_case_detail(self):
        """Test getting case detail"""
        if not self.case_id:
            self.log_result("Get Case Detail", False, "No case_id available")
            return False
        success, response = self.run_test("Get Case Detail", "GET", f"cases/{self.case_id}", 200)
        return success

    def test_screening_run(self):
        """Test running screening"""
        if not self.case_id:
            self.log_result("Run Screening", False, "No case_id available")
            return False
        
        screening_data = {"case_id": self.case_id, "run_type": "sanctions"}
        success, response = self.run_test("Run Sanctions Screening", "POST", "screening/run", 200, screening_data)
        return success

    def test_risk_assessment(self):
        """Test risk assessment"""
        if not self.case_id:
            self.log_result("Risk Assessment", False, "No case_id available")
            return False
            
        risk_data = {"case_id": self.case_id, "inputs": {}}
        success, response = self.run_test("Risk Assessment", "POST", "risk/assess", 200, risk_data)
        return success

    def test_kyc_export(self):
        """Test KYC export"""
        if not self.case_id:
            self.log_result("KYC Export", False, "No case_id available")
            return False
            
        success, response = self.run_test("KYC Export", "POST", f"export/kyc/{self.case_id}", 200)
        return success

    def test_customer_portal_endpoints(self):
        """Test customer portal OTP flow"""
        # Test OTP request
        otp_request_data = {
            "email": "test-customer@example.com",
            "tenant_id": self.tenant_id if self.tenant_id else "demo-tenant",
            "case_ref": "DDY-TEST-001"
        }
        success1, response1 = self.run_test("Customer OTP Request", "POST", "auth/customer/otp-request", 200, otp_request_data)
        
        # Test OTP verify
        if success1:
            otp_verify_data = {
                "email": "test-customer@example.com",
                "code": "123456",  # Demo OTP
                "tenant_id": self.tenant_id if self.tenant_id else "demo-tenant"
            }
            success2, response2 = self.run_test("Customer OTP Verify", "POST", "auth/customer/otp-verify", 200, otp_verify_data)
            return success2
        return False

    def test_mi_endpoints(self):
        """Test MI (Management Information) endpoints"""
        success1, _ = self.run_test("MI Global Stats", "GET", "mi/global", 200)
        
        if self.tenant_id:
            success2, _ = self.run_test("MI Tenant Stats", "GET", f"mi/tenant/{self.tenant_id}", 200)
            return success1 and success2
        return success1

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting DDYs Compliance API Tests")
        print(f"Testing against: {self.base_url}")
        print("=" * 50)

        # Basic health checks
        self.test_health_check()
        self.test_seed_data()

        # Authentication tests
        admin_login_success = self.test_admin_login()
        self.test_maker_login()
        self.test_customer_login()

        if admin_login_success:
            # Core functionality tests (require auth)
            self.test_get_tenants()
            self.test_get_cases()
            self.test_create_case()
            self.test_get_case_detail()
            self.test_screening_run()
            self.test_risk_assessment()
            self.test_kyc_export()
            self.test_customer_portal_endpoints()
            self.test_mi_endpoints()
        else:
            print("⚠️ Admin login failed - skipping authenticated tests")

        # Print results
        print("=" * 50)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed < self.tests_run:
            print("❌ Some tests failed. Details:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - {result['test_name']}: {result['message']}")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test runner"""
    tester = DDYsComplianceAPITester()
    success = tester.run_all_tests()
    
    # Save detailed results
    with open('/app/test_reports/api_test_results.json', 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": tester.tests_run,
            "passed_tests": tester.tests_passed,
            "success_rate": f"{(tester.tests_passed/tester.tests_run)*100:.1f}%" if tester.tests_run > 0 else "0%",
            "results": tester.results
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/test_reports/api_test_results.json")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())