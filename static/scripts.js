document.getElementById('send-btn').addEventListener('click', () => {
    const userInput = document.getElementById('user-input').value;
    if (!userInput.trim()) return;

    const chatBox = document.getElementById('chat-box');
    const escapeHTML = (str) => {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    const sanitizedInput = escapeHTML(userInput);
    chatBox.innerHTML += `<div class="user-message"><b>You:</b> ${sanitizedInput}</div>`;
    document.getElementById('user-input').value = '';

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userInput })
    })
    .then(response => response.json())
    .then(data => {
        if (data.reply) {
            chatBox.innerHTML += `<div class="bot-message"><b>Bot:</b> ${escapeHTML(data.reply)}</div>`;
        } else if (data.error) {
            chatBox.innerHTML += `<div class="bot-message"><b>Bot:</b> Error: ${data.error}</div>`;
        } else {
            chatBox.innerHTML += `<div class="bot-message"><b>Bot:</b> Unexpected response</div>`;
        }
        setTimeout(() => {
            chatBox.scrollTop = chatBox.scrollHeight;
        }, 100);
    })
    .catch(error => {
        chatBox.innerHTML += `<div class="bot-message"><b>Bot:</b> Sorry, something went wrong. Please try again later.</div>`;
    });
});
