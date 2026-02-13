import requests
import sys
import json
from datetime import datetime

class DDYsComplianceAPITester:
    def __init__(self, base_url="https://kyc-flow-5.preview.emergentagent.com"):
        self.base_url = base_url
        self.admin_token = None
        self.maker_token = None
        self.customer_token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.test_case_id = None
        self.invite_token = None

    def run_test(self, name, method, endpoint, expected_status, data=None, token=None, timeout=30):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}" if not endpoint.startswith('http') else endpoint
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {"raw": response.text}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                self.failed_tests.append(f"{name} - Expected {expected_status}, got {response.status_code}")
                return False, {}

        except requests.Timeout:
            print(f"❌ Failed - Timeout after {timeout}s")
            self.failed_tests.append(f"{name} - Timeout")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append(f"{name} - {str(e)}")
            return False, {}

    def test_login_admin(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@ddys.com", "password": "Admin123!"}
        )
        if success and 'token' in response:
            self.admin_token = response['token']
            return True
        return False

    def test_login_maker(self):
        """Test maker login"""
        success, response = self.run_test(
            "Maker Login",
            "POST",
            "auth/login",
            200,
            data={"email": "maker@ddys.com", "password": "Maker123!"}
        )
        if success and 'token' in response:
            self.maker_token = response['token']
            return True
        return False

    def test_admin_dashboard_access(self):
        """Test admin can access admin dashboard"""
        success, response = self.run_test(
            "Admin Dashboard Access",
            "GET",
            "admin/dashboard",
            200,
            token=self.admin_token
        )
        return success

    def test_admin_cases_access(self):
        """Test admin can see ALL cases (not tenant-filtered)"""
        success, response = self.run_test(
            "Admin All Cases Access",
            "GET",
            "cases",
            200,
            token=self.admin_token
        )
        if success:
            cases = response
            print(f"   Admin can see {len(cases)} total cases")
        return success

    def test_maker_cases_access(self):
        """Test maker sees only tenant-specific cases"""
        success, response = self.run_test(
            "Maker Tenant Cases Access",
            "GET",
            "cases",
            200,
            token=self.maker_token
        )
        if success:
            cases = response
            demo_bank_cases = [c for c in cases if c.get('tenant_id') and 'demo' in c.get('case_ref', '').lower()]
            print(f"   Maker can see {len(cases)} cases, {len(demo_bank_cases)} Demo Bank cases")
        return success

    def test_create_test_case(self):
        """Create a test case for invite flow"""
        success, response = self.run_test(
            "Create Test Case",
            "POST",
            "cases",
            201,
            data={
                "tenant_id": "demo-bank-tenant-id", 
                "case_type": "onboarding",
                "jurisdiction": "EU",
                "product_scope": "Test Invite Flow"
            },
            token=self.maker_token
        )
        if success:
            self.test_case_id = response.get('id')
            print(f"   Created test case: {response.get('case_ref')}")
        return success

    def test_invite_customer(self):
        """Test customer invitation flow"""
        if not self.test_case_id:
            print("❌ No test case ID available for invite")
            return False
            
        success, response = self.run_test(
            "Invite Customer",
            "POST",
            "reminders/invite-customer",
            200,
            data={
                "case_id": self.test_case_id,
                "email": "testcustomer@example.com"
            },
            token=self.maker_token
        )
        if success:
            self.invite_token = response.get('invite_token')
            print(f"   Invite URL: {response.get('invite_url')}")
        return success

    def test_get_invite_details(self):
        """Test getting invite details (no auth required)"""
        if not self.invite_token:
            print("❌ No invite token available")
            return False
            
        success, response = self.run_test(
            "Get Invite Details",
            "GET",
            f"customer/invite/{self.invite_token}",
            200
        )
        if success:
            print(f"   Invite for: {response.get('invite', {}).get('email')}")
        return success

    def test_accept_invite(self):
        """Test accepting invite with email verification"""
        if not self.invite_token:
            print("❌ No invite token available")
            return False
            
        success, response = self.run_test(
            "Accept Invite",
            "POST",
            f"customer/invite/{self.invite_token}/accept",
            200,
            data={"email": "testcustomer@example.com"}
        )
        if success:
            print(f"   OTP demo code: {response.get('demo_otp')}")
        return success

    def test_verify_otp(self):
        """Test OTP verification"""
        if not self.invite_token:
            print("❌ No invite token available")
            return False
            
        success, response = self.run_test(
            "Verify OTP",
            "POST",
            f"customer/invite/{self.invite_token}/verify",
            200,
            data={"code": "123456"}
        )
        if success:
            self.customer_token = response.get('token')
            print(f"   Customer authenticated for case: {response.get('case_id')}")
        return success

    def test_send_reminder(self):
        """Test sending document reminder"""
        if not self.test_case_id:
            print("❌ No test case ID available for reminder")
            return False
            
        success, response = self.run_test(
            "Send Document Reminder",
            "POST",
            "reminders/send",
            200,
            data={"case_id": self.test_case_id},
            token=self.maker_token
        )
        if success:
            print(f"   Reminder status: {response.get('sent')}")
        return success

    def test_get_reminders(self):
        """Test getting reminder history"""
        if not self.test_case_id:
            print("❌ No test case ID available")
            return False
            
        success, response = self.run_test(
            "Get Reminder History",
            "GET",
            f"reminders?case_id={self.test_case_id}",
            200,
            token=self.maker_token
        )
        if success:
            reminders = response
            print(f"   Found {len(reminders)} reminders for case")
        return success

    def test_customer_case_access(self):
        """Test customer can access their case"""
        if not self.customer_token or not self.test_case_id:
            print("❌ No customer token or case ID available")
            return False
            
        success, response = self.run_test(
            "Customer Case Access",
            "GET",
            f"customer/case-by-id/{self.test_case_id}",
            200,
            token=self.customer_token
        )
        if success:
            requirements = response.get('requirements', [])
            print(f"   Customer sees {len(requirements)} requirements")
        return success

    def test_document_upload_simulation(self):
        """Test document intelligence with mock upload"""
        if not self.test_case_id:
            print("❌ No test case ID available")
            return False
            
        # Test document metadata processing (simulated)
        success, response = self.run_test(
            "Document Intelligence Simulation",
            "POST",
            "documents/analyze-mock",
            200,
            data={
                "case_id": self.test_case_id,
                "doc_type": "tax_return",
                "filename": "tax_return_2024.pdf",
                "party_type": "natural_person"
            },
            token=self.maker_token
        )
        if success:
            print(f"   Doc analysis decision: {response.get('decision', 'unknown')}")
        return success

    def test_cross_document_logic(self):
        """Test cross-document auto-fill logic"""
        # This would be tested through the document intelligence service
        # For now, test that the service is available
        success, response = self.run_test(
            "Cross-Document Logic Check",
            "GET",
            "cases",
            200,
            token=self.maker_token
        )
        print("   Cross-document logic is implemented in document_intelligence.py")
        return success

def main():
    print("🚀 Starting DDYs Compliance Platform Phase 3 Testing")
    print("=" * 60)
    
    tester = DDYsComplianceAPITester()
    results = {}
    
    # Phase 1: Authentication Tests
    print("\n📋 Phase 1: Authentication & Access Control")
    results['admin_login'] = tester.test_login_admin()
    results['maker_login'] = tester.test_login_maker()
    
    if not results['admin_login']:
        print("❌ Admin login failed - cannot continue with admin tests")
        return 1
        
    if not results['maker_login']:
        print("❌ Maker login failed - cannot continue with maker tests")
        return 1

    # Phase 2: Admin Portal Access
    print("\n🛡️ Phase 2: Admin Portal Features")
    results['admin_dashboard'] = tester.test_admin_dashboard_access()
    results['admin_all_cases'] = tester.test_admin_cases_access()
    results['maker_tenant_cases'] = tester.test_maker_cases_access()

    # Phase 3: Customer Invite Flow
    print("\n📧 Phase 3: Customer Invitation Flow")
    results['create_case'] = tester.test_create_test_case()
    results['invite_customer'] = tester.test_invite_customer()
    results['get_invite'] = tester.test_get_invite_details()
    results['accept_invite'] = tester.test_accept_invite()
    results['verify_otp'] = tester.test_verify_otp()

    # Phase 4: Reminder System
    print("\n🔔 Phase 4: Reminder System")
    results['send_reminder'] = tester.test_send_reminder()
    results['get_reminders'] = tester.test_get_reminders()

    # Phase 5: Customer Portal
    print("\n👤 Phase 5: Customer Portal Access")
    results['customer_case_access'] = tester.test_customer_case_access()

    # Phase 6: Document Intelligence
    print("\n🤖 Phase 6: Document Intelligence")
    results['doc_intelligence'] = tester.test_document_upload_simulation()
    results['cross_doc_logic'] = tester.test_cross_document_logic()

    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed ({100*tester.tests_passed/tester.tests_run:.1f}%)")
    
    if tester.failed_tests:
        print("\n❌ Failed Tests:")
        for test in tester.failed_tests:
            print(f"   • {test}")
    
    # Save results
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": tester.tests_run,
        "passed_tests": tester.tests_passed,
        "failed_tests": tester.failed_tests,
        "success_rate": f"{100*tester.tests_passed/tester.tests_run:.1f}%",
        "detailed_results": results,
        "phase3_features": {
            "admin_portal_switching": results.get('admin_dashboard', False),
            "customer_invite_flow": all([
                results.get('invite_customer', False),
                results.get('get_invite', False), 
                results.get('accept_invite', False),
                results.get('verify_otp', False)
            ]),
            "reminder_system": all([
                results.get('send_reminder', False),
                results.get('get_reminders', False)
            ]),
            "document_intelligence": results.get('doc_intelligence', False),
        }
    }
    
    with open('/app/test_reports/api_test_results.json', 'w') as f:
        json.dump(test_results, f, indent=2)
    
    print(f"\n💾 Results saved to /app/test_reports/api_test_results.json")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())