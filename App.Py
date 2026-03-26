import sys
import subprocess
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
import socket

# --- CONFIGURACIÓN ---
CLAUDE_API_KEY = "TU_API_KEY_AQUI" 
CLAUDE_MODEL   = "claude-3-5-sonnet-20240620"
SYSTEM_PROMPT  = "Eres un asistente de voz fluido. Responde de forma breve y natural en español."

app = Flask(__name__)
CORS(app)
historial = []

HTML_REDISEÑADO = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Chat de Voz IA</title>
    <style>
        :root { --bg: #0f172a; --accent: #38bdf8; --user-msg: #1e293b; --ai-msg: #0f172a; --text: #f8fafc; }
        * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
        body { font-family: sans-serif; background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
        
        header { padding: 15px; text-align: center; border-bottom: 1px solid #334155; background: #1e293b; }
        #chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 15px; }
        
        .msg { max-width: 80%; padding: 12px 16px; border-radius: 20px; font-size: 15px; line-height: 1.4; animation: slide 0.2s ease; }
        @keyframes slide { from { opacity: 0; transform: translateY(10); } to { opacity: 1; transform: translateY(0); } }
        .user { align-self: flex-end; background: var(--user-msg); border-bottom-right-radius: 4px; color: var(--accent); }
        .ai { align-self: flex-start; background: var(--ai-msg); border: 1px solid #334155; border-bottom-left-radius: 4px; }

        #controls { padding: 30px; background: #1e293b; display: flex; flex-direction: column; align-items: center; gap: 15px; border-top: 1px solid #334155; }
        #status { font-size: 13px; color: var(--accent); min-height: 20px; font-weight: bold; }
        
        /* BOTÓN ESTILO GÉMINIS */
        #mic-btn {
            width: 80px; height: 80px; border-radius: 50%; border: none;
            background: var(--accent); color: #0f172a; font-size: 32px;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.4); transition: all 0.2s;
            user-select: none; -webkit-user-select: none;
        }
        #mic-btn:active { transform: scale(0.9); background: #f43f5e; box-shadow: 0 0 30px rgba(244, 63, 94, 0.6); }
        .recording { animation: pulse 1.5s infinite; background: #f43f5e !important; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.7); } 70% { box-shadow: 0 0 0 20px rgba(244, 63, 94, 0); } 100% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); } }
    </style>
</head>
<body>
    <header><h3>Asistente IA Voz</h3></header>
    <div id="chat"></div>
    <div id="controls">
        <div id="status">Presiona para hablar</div>
        <button id="mic-btn">🎙️</button>
        <p style="font-size: 10px; opacity: 0.5;">Mantén presionado para hablar</p>
    </div>

    <script>
        const btn = document.getElementById('mic-btn');
        const status = document.getElementById('status');
        const chat = document.getElementById('chat');
        let recognition;
        let finalTranscript = "";

        // Inicializar reconocimiento de voz
        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.lang = 'es-ES';
            recognition.interimResults = false;
            recognition.continuous = false;

            recognition.onstart = () => { 
                status.innerText = "Escuchando..."; 
                btn.classList.add('recording');
            };
            
            recognition.onresult = (event) => {
                finalTranscript = event.results[0][0].transcript;
            };

            recognition.onend = () => {
                btn.classList.remove('recording');
                status.innerText = "Procesando...";
                if(finalTranscript) {
                    addMsg('user', finalTranscript);
                    sendToIA(finalTranscript);
                    finalTranscript = "";
                } else {
                    status.innerText = "No se escuchó nada";
                }
            };

            recognition.onerror = (e) => {
                status.innerText = "Error: " + e.error;
                btn.classList.remove('recording');
            };
        } else {
            status.innerText = "Micrófono no soportado en este navegador";
        }

        // Lógica de presionar y soltar (Push to Talk)
        btn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            window.speechSynthesis.cancel();
            finalTranscript = "";
            recognition.start();
        });

        btn.addEventListener('touchend', (e) => {
            e.preventDefault();
            recognition.stop();
        });

        // Enviar a Python
        async function sendToIA(text) {
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text})
                });
                const data = await res.json();
                addMsg('ai', data.response);
                speak(data.response);
                status.innerText = "Listo";
            } catch (e) {
                addMsg('ai', "Error de conexión");
            }
        }

        function addMsg(role, text) {
            const div = document.createElement('div');
            div.className = 'msg ' + (role === 'user' ? 'user' : 'ai');
            div.innerText = text;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function speak(text) {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'es-ES';
            window.speechSynthesis.speak(utterance);
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index(): return render_template_string(HTML_REDISEÑADO)

@app.route("/chat", methods=["POST"])
def chat():
    global historial
    data = request.get_json()
    msg = data.get("message")
    historial.append({"role": "user", "content": msg})
    
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 512,
                "system": SYSTEM_PROMPT,
                "messages": historial,
            },
            timeout=30
        )
        respuesta = resp.json()["content"][0]["text"]
        historial.append({"role": "assistant", "content": respuesta})
        return jsonify({"response": respuesta})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
