# FaeNet v4 — Guia de Deploy e APK Android

---

## 📦 O que mudou na v4

| Antes (v3) | Agora (v4) |
|-----------|-----------|
| Dados em memória RAM (apagam ao reiniciar) | **PostgreSQL** com SQLAlchemy |
| Senhas em texto puro | **bcrypt** (werkzeug hashing) |
| Sem suporte a Docker | **Dockerfile + docker-compose** |
| Sem suporte a deploy cloud | **Railway / Render / VPS** |
| Apenas web browser | **+ APK Android** via Capacitor |

---

## 🚀 PARTE 1 — Hospedar o site

### Opção A: Railway (RECOMENDADO — mais fácil, grátis até 5$/mês)

**Railway** detecta automaticamente Flask e provisiona um PostgreSQL.

#### Passo a passo:

1. **Crie uma conta** em [railway.app](https://railway.app)

2. **Instale o Railway CLI** (opcional, facilita):
   ```bash
   npm install -g @railway/cli
   railway login
   ```

3. **Crie um novo projeto no Railway:**
   - Clique em **New Project → Deploy from GitHub repo**
   - Faça upload do seu código para um repositório GitHub primeiro:
     ```bash
     git init
     git add .
     git commit -m "FaeNet v4"
     git remote add origin https://github.com/SEU_USUARIO/faenet.git
     git push -u origin main
     ```

4. **Adicione um banco PostgreSQL:**
   - No dashboard do Railway: clique em **+ New → Database → PostgreSQL**
   - O Railway cria automaticamente a variável `DATABASE_URL`

5. **Configure as variáveis de ambiente** no Railway (Settings → Variables):
   ```
   SECRET_KEY=sua_chave_muito_secreta_aleatoria_aqui
   PORT=5000
   ```
   > Gere uma SECRET_KEY segura: `python -c "import secrets; print(secrets.token_hex(32))"`

6. **Deploy automático** — toda vez que você fizer `git push`, o Railway redeploy.

7. Acesse a URL gerada (ex: `https://faenet-production.up.railway.app`)

**O banco é criado automaticamente** pelo `db.create_all()` que roda no startup.

---

### Opção B: Render (grátis com limitações)

1. Crie conta em [render.com](https://render.com)
2. **New → Web Service → Connect GitHub**
3. Escolha seu repositório
4. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
5. **Adicione PostgreSQL:** New → PostgreSQL (plano Free)
6. Copie a `Internal Database URL` e adicione como variável `DATABASE_URL`
7. Adicione `SECRET_KEY` nas variáveis de ambiente

> ⚠️ No plano gratuito do Render, o serviço "dorme" após 15 min de inatividade.
> Para evitar isso, use [UptimeRobot](https://uptimerobot.com) para fazer ping a cada 5 min.

---

### Opção C: VPS (DigitalOcean, Contabo, Linode)

Para ter controle total e hospedar uploads permanentemente:

#### 1. No servidor (Ubuntu 22.04):

```bash
# Atualiza sistema
sudo apt update && sudo apt upgrade -y

# Instala dependências
sudo apt install -y python3-pip python3-venv postgresql postgresql-contrib nginx certbot python3-certbot-nginx

# Configura PostgreSQL
sudo -u postgres psql << SQL
CREATE USER faenet WITH PASSWORD 'senha_forte_aqui';
CREATE DATABASE faenet OWNER faenet;
GRANT ALL PRIVILEGES ON DATABASE faenet TO faenet;
\q
SQL

# Clona o projeto
cd /var/www
sudo git clone https://github.com/SEU_USUARIO/faenet.git
sudo chown -R $USER:$USER faenet
cd faenet

# Cria ambiente virtual
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Cria .env
cat > .env << EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=postgresql://faenet:senha_forte_aqui@localhost/faenet
PORT=5000
EOF
```

#### 2. Configura serviço systemd:

```bash
sudo nano /etc/systemd/system/faenet.service
```

```ini
[Unit]
Description=FaeNet Flask App
After=network.target postgresql.service

[Service]
User=www-data
WorkingDirectory=/var/www/faenet
Environment="PATH=/var/www/faenet/venv/bin"
EnvironmentFile=/var/www/faenet/.env
ExecStartPre=/var/www/faenet/venv/bin/python -c "from app import app, db, seed_db; app.app_context().push(); db.create_all(); seed_db()"
ExecStart=/var/www/faenet/venv/bin/gunicorn app:app --bind 127.0.0.1:5000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable faenet
sudo systemctl start faenet
sudo systemctl status faenet
```

#### 3. Configura Nginx (proxy reverso):

```bash
sudo nano /etc/nginx/sites-available/faenet
```

```nginx
server {
    listen 80;
    server_name SEU_DOMINIO.com www.SEU_DOMINIO.com;

    client_max_body_size 20M;

    location /static/uploads/ {
        alias /var/www/faenet/static/uploads/;
        expires 30d;
    }

    location /static/ {
        alias /var/www/faenet/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/faenet /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# HTTPS gratuito com Let's Encrypt
sudo certbot --nginx -d SEU_DOMINIO.com -d www.SEU_DOMINIO.com
```

---

### Opção D: Docker (qualquer servidor com Docker)

```bash
# Sobe com PostgreSQL em um comando só
docker compose up -d

# Logs
docker compose logs -f web

# Parar
docker compose down

# Para fazer backup do banco
docker compose exec db pg_dump -U faenet faenet > backup.sql
```

---

## 📱 PARTE 2 — APK Android com Capacitor

O Capacitor transforma o site Flask em um app Android **nativo** que roda dentro de uma WebView, mas com acesso a recursos nativos do telefone.

### Pré-requisitos no seu computador:

- **Node.js 18+**: [nodejs.org](https://nodejs.org)
- **Android Studio**: [developer.android.com/studio](https://developer.android.com/studio)
- **Java 17+** (vem com Android Studio)
- Python 3.11+ e as dependências do FaeNet

---

### PASSO 1: Preparar o projeto web estático

O Capacitor precisa de arquivos estáticos HTML/JS/CSS.  
Vamos criar uma pasta `www/` com todos os assets da FaeNet:

```bash
# Na pasta do faenet4
mkdir -p www/static/css www/static/js

# Copia os assets
cp static/css/app.css www/static/css/
cp static/js/app.js www/static/js/

# Cria o index.html principal (shell da SPA)
```

**Criar `www/index.html`** com o conteúdo abaixo (ajusta a URL do servidor):

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>
  <title>FaeNet</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet"/>
  <link rel="stylesheet" href="static/css/app.css"/>
  <style>
    /* Status bar segura no Android */
    body { padding-top: env(safe-area-inset-top); }
    /* Loading screen */
    #app-loading {
      position: fixed; inset: 0; background: #080e1d;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      z-index: 9999; gap: 16px;
    }
    .load-gem {
      width: 60px; height: 60px; border-radius: 16px;
      background: linear-gradient(135deg, #0ea5e9, #6366f1);
      display: flex; align-items: center; justify-content: center;
      font-size: 28px; font-weight: 800; color: #fff;
      font-family: 'Syne', sans-serif;
      box-shadow: 0 8px 32px rgba(14,165,233,.4);
      animation: pulse 1.5s ease-in-out infinite;
    }
    @keyframes pulse { 0%,100%{transform:scale(1)} 50%{transform:scale(1.08)} }
    .load-title { font-family:'Syne',sans-serif; font-size:24px; font-weight:700; color:#f1f5f9; }
    .load-sub { font-size:13px; color:#64748b; }
  </style>
</head>
<body>
<div id="app-loading">
  <div class="load-gem">F</div>
  <div class="load-title">FaeNet</div>
  <div class="load-sub">Carregando...</div>
</div>
<div id="app-root" style="display:none"></div>

<script>
  // URL BASE DO SERVIDOR — TROQUE PELA SUA URL DE PRODUÇÃO
  const API_BASE = 'https://SEU-SITE.railway.app';

  // Wrapper de fetch que aponta para o servidor real
  const _origFetch = window.fetch.bind(window);
  window.fetch = (url, opts) => {
    if (url.startsWith('/')) url = API_BASE + url;
    return _origFetch(url, { ...opts, credentials: 'include' });
  };

  // Verificar se está logado
  async function checkAuth() {
    try {
      const r = await fetch('/api/me');
      if (r.ok) {
        showApp();
      } else {
        showLogin();
      }
    } catch (e) {
      showError();
    }
  }

  function showApp() {
    document.getElementById('app-loading').style.display = 'none';
    document.getElementById('app-root').style.display = '';
    document.getElementById('app-root').innerHTML = `
      <iframe 
        src="${API_BASE}/feed"
        style="width:100%;height:100vh;border:none;background:#080e1d"
        id="main-iframe"
      ></iframe>`;
  }

  function showLogin() {
    document.getElementById('app-loading').style.display = 'none';
    document.getElementById('app-root').style.display = '';
    document.getElementById('app-root').innerHTML = `
      <iframe 
        src="${API_BASE}/"
        style="width:100%;height:100vh;border:none;background:#080e1d"
        id="main-iframe"
      ></iframe>`;
  }

  function showError() {
    document.querySelector('.load-sub').textContent = 'Sem conexão. Verifique sua internet.';
    document.querySelector('.load-gem').textContent = '!';
    setTimeout(checkAuth, 3000);
  }

  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(checkAuth, 800);
  });
</script>
</body>
</html>
```

---

### PASSO 2: Inicializar o projeto Capacitor

```bash
# Na pasta raiz do faenet4
npm init -y

# Instala Capacitor
npm install @capacitor/core @capacitor/cli @capacitor/android

# Inicializa o Capacitor
npx cap init "FaeNet" "com.faetec.faenet" --web-dir www
```

Isso cria o arquivo `capacitor.config.json`:

```json
{
  "appId": "com.faetec.faenet",
  "appName": "FaeNet",
  "webDir": "www",
  "server": {
    "url": "https://SEU-SITE.railway.app",
    "cleartext": true,
    "androidScheme": "https"
  },
  "android": {
    "allowMixedContent": true,
    "captureInput": true,
    "webContentsDebuggingEnabled": false
  },
  "plugins": {
    "SplashScreen": {
      "launchShowDuration": 2000,
      "backgroundColor": "#080e1d",
      "androidSplashResourceName": "splash",
      "showSpinner": false
    }
  }
}
```

> ⚠️ **IMPORTANTE:** Substitua `https://SEU-SITE.railway.app` pela URL real do seu servidor Railway/Render.

---

### PASSO 3: Adicionar a plataforma Android

```bash
# Adiciona Android
npx cap add android

# Sincroniza os arquivos web
npx cap sync android
```

---

### PASSO 4: Configurar o Android nativo

#### 4a. Abre no Android Studio:
```bash
npx cap open android
```

#### 4b. No Android Studio, edite `android/app/src/main/AndroidManifest.xml`:

Adicione DENTRO de `<application>`:
```xml
android:usesCleartextTraffic="true"
```

E ANTES de `</manifest>`, adicione as permissões:
```xml
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"/>
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"/>
<uses-permission android:name="android.permission.CAMERA"/>
```

#### 4c. Ícone e Splash Screen

Coloque seu ícone em:
- `android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png` (192x192px)
- `android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png` (144x144px)
- `android/app/src/main/res/mipmap-xhdpi/ic_launcher.png` (96x96px)
- `android/app/src/main/res/mipmap-hdpi/ic_launcher.png` (72x72px)
- `android/app/src/main/res/mipmap-mdpi/ic_launcher.png` (48x48px)

Ou use o **Image Asset Studio** do Android Studio:
- `File → New → Image Asset`
- Tipo: Launcher Icons
- Source Asset: escolha uma imagem quadrada

---

### PASSO 5: Gerar o APK

#### Modo Debug (para testar):
```bash
# No Android Studio: Build → Build Bundle(s) / APK(s) → Build APK(s)
# Ou via linha de comando:
cd android
./gradlew assembleDebug
```

O APK debug fica em:
```
android/app/build/outputs/apk/debug/app-debug.apk
```

#### Modo Release (para publicar):

1. **Gera uma keystore** (guarde este arquivo com segurança!):
```bash
keytool -genkey -v \
  -keystore faenet-release.keystore \
  -alias faenet \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000
```

2. **Configura a assinatura** em `android/app/build.gradle`:
```groovy
android {
    signingConfigs {
        release {
            storeFile file("../../faenet-release.keystore")
            storePassword "SUA_SENHA"
            keyAlias "faenet"
            keyPassword "SUA_SENHA"
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
            minifyEnabled false
        }
    }
}
```

3. **Gera o APK release:**
```bash
cd android
./gradlew assembleRelease
```

O APK fica em:
```
android/app/build/outputs/apk/release/app-release.apk
```

---

### PASSO 6: Instalar no celular

#### Via USB (modo Developer):
1. No Android: Configurações → Sobre o telefone → toque 7x em "Número da versão"
2. Configurações → Opções do desenvolvedor → Depuração USB: **ativar**
3. Conecte o cabo USB
```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

#### Via arquivo (Instalar APK diretamente):
1. Transfira o arquivo `.apk` para o celular (WhatsApp, Google Drive, etc.)
2. No Android: Configurações → Segurança → Instalar apps de fontes desconhecidas: **ativar**
3. Abra o arquivo `.apk` e instale

---

### PASSO 7 (Opcional): Publicar na Google Play Store

1. Crie uma conta de desenvolvedor em [play.google.com/console](https://play.google.com/console) (taxa única de $25)
2. Gere um **App Bundle** (melhor que APK para a Play Store):
```bash
cd android
./gradlew bundleRelease
# Arquivo: android/app/build/outputs/bundle/release/app-release.aab
```
3. No Google Play Console: Create app → Upload o `.aab`
4. Preencha as informações, screenshots, política de privacidade
5. Envie para revisão (1-3 dias úteis)

---

## 🔒 Segurança em produção

### Variáveis obrigatórias (nunca commite no git!):
```bash
# Adicione ao .gitignore
echo ".env" >> .gitignore
echo "faenet-release.keystore" >> .gitignore
echo "*.db" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "static/uploads/" >> .gitignore
```

### Recomendações:
- **SECRET_KEY**: sempre gere com `secrets.token_hex(32)`, mínimo 32 chars
- **Banco de dados**: use `postgresql://` com senha forte em produção
- **HTTPS**: sempre obrigatório em produção (Railway/Render já incluem)
- **Uploads**: considere usar **Cloudinary** ou **AWS S3** para arquivos em produção

---

## 📊 Resumo de custos estimados

| Plataforma | Custo | Banco | Ideal para |
|-----------|-------|-------|-----------|
| Railway | Grátis ($5 crédito/mês) | PostgreSQL incluído | ✅ Escola/teste |
| Render | Grátis (com sleep) | PostgreSQL gratuito | ✅ Escola/teste |
| Render Pago | $7/mês | PostgreSQL $7/mês | Produção pequena |
| VPS Contabo | €4/mês | Self-hosted | Produção maior |
| DigitalOcean | $6/mês | Managed $15/mês | Produção profissional |

---

## ❓ FAQ

**P: Os dados somem quando o servidor reinicia?**  
R: Não! Com PostgreSQL, os dados ficam salvos permanentemente.

**P: As fotos ficam guardadas?**  
R: No Railway/Render, o disco é efêmero — fotos podem sumir ao redeploy. Use **Cloudinary** (gratuito até 25GB) para guardar imagens definitivamente.

**P: O APK funciona sem internet?**  
R: Não — ele carrega o site do servidor. Para funcionar offline, seria necessário um Service Worker (PWA), o que é uma etapa futura.

**P: Posso usar domínio próprio (ex: faenet.com.br)?**  
R: Sim! Railway e Render permitem domínio customizado gratuitamente. Compre um domínio no [Registro.br](https://registro.br) (~R$40/ano).

**P: Quantos usuários aguenta?**  
R: Railway/Render com 1 worker: ~50-100 usuários simultâneos. Para mais, aumente os workers no Procfile.
