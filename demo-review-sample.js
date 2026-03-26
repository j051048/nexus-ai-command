// 示例代码：需要审查的登录函数
async function loginUser(email, password) {
    const response = await fetch('/api/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
    });
    const data = await response.json();
    localStorage.setItem('token', data.token);
    return data;
}

function validateEmail(email) {
    return email.includes('@');
}
