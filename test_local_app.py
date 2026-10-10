
import urllib.request, json, uuid

base_url = "http://127.0.0.1:8000/api"
email = f"local_{uuid.uuid4().hex[:6]}@example.com"
req = urllib.request.Request(f"{base_url}/auth/register/applicant/", data=json.dumps({
    'email': email,
    'full_name': 'Local Tester',
    'phone': '+2348011223344',
    'country': 'Nigeria',
    'password': 'LocalPassword123'
}).encode('utf-8'), headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access']

app_data = {
    'full_name': 'Local Tester',
    'email': email,
    'phone': '+2348011223344',
    'origin_country': 'Nigeria',
    'destination_country': 'Canada',
    'previous_schools': 'University of Lagos',
    'qualification': "Bachelor's Degree",
    'year_graduated': 2023,
    'grade_gpa': '3.8/4.0',
    'institution': 'sheridan-college',
    'program_ids': [430],
    'is_custom_course': False,
    'custom_course_name': '',
}
try:
    req2 = urllib.request.Request(f"{base_url}/applications/", data=json.dumps(app_data).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    resp2 = urllib.request.urlopen(req2)
    print('Local create SUCCESS:', resp2.status, resp2.read().decode()[:200])
except urllib.error.HTTPError as e:
    print('Local create FAILED:', e.code, e.read().decode()[:400])
except Exception as e:
    print('Error:', e)
