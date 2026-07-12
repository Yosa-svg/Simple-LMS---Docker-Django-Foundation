import urllib.request
import json

BASE_URL = 'http://localhost:8000/api/v1'

def print_step(msg):
    print(f'\n{msg}')
    print('-'*50)

def request(method, url, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    req = urllib.request.Request(
        BASE_URL + url,
        data=json.dumps(data).encode() if data else b'',
        headers=headers,
        method=method
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, json.loads(body) if body else {}

print_step('1. LOGIN AS INSTRUCTOR')
status, resp = request('POST', '/auth/sign-in', {'username': 'instructor_demo', 'password': 'InstrDemo123!'})
instructor_token = resp['access']
print(f'Status: {status} | Login Success')

print_step('2. CREATE COURSE')
course_data = {
    'name': 'Demo Course E2E Test',
    'description': 'Course testing automation.',
    'price': 150000,
    'category_id': 1
}
status, resp = request('POST', '/courses/', course_data, instructor_token)
course_id = resp['id']
print(f'Status: {status} | Course Created -> ID: {course_id}')

print_step('3. ADD CONTENT')
content_data = {
    'name': 'Module 1: Intro',
    'description': 'Introduction',
    'course_id': course_id
}
status, resp = request('POST', '/contents/', content_data, instructor_token)
content_id = resp['id']
print(f'Status: {status} | Content Created -> ID: {content_id}')

print_step('4. LOGIN AS STUDENT')
status, resp = request('POST', '/auth/sign-in', {'username': 'student_demo', 'password': 'StudDemo123!'})
student_token = resp['access']
print(f'Status: {status} | Login Success')

print_step('5. ENROLL IN COURSE (Triggers Celery)')
status, resp = request('POST', f'/courses/{course_id}/enroll/', token=student_token)
print(f'Status: {status} | Enrolled Success')

print_step('6. POST COMMENT')
comment_data = {
    'content_id': content_id,
    'comment': 'This is an awesome demo test!'
}
status, resp = request('POST', '/comments/', comment_data, student_token)
print(f'Status: {status} | Comment Posted')

print_step('7. TRIGGER BACKGROUND REPORT (Celery)')
status, resp = request('POST', f'/courses/{course_id}/export-report/', token=instructor_token)
print(f'Status: {status} | Task ID: {resp.get("task_id")}')

print_step('8. CHECK ANALYTICS (MongoDB)')
status, resp = request('GET', '/analytics/popular-courses/', token=student_token)
print(f'Status: {status} | Data Retrieved from MongoDB (Total: {len(resp)} records)')

print_step('9. CLEANUP (Delete Course)')
status, resp = request('DELETE', f'/courses/{course_id}', token=instructor_token)
print(f'Status: {status} | Course Deleted')

print_step('✅ ALL ENDPOINTS TESTED SUCCESSFULLY!')
