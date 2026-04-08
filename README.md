# FaeNet v2 🎓 — Rede Social FAETEC

Rede social escolar completa com Python (Flask), HTML, CSS e JavaScript.

## Estrutura

```
faenet/
├── app.py                  ← Flask backend + API REST completa
├── requirements.txt
├── templates/
│   ├── login.html          ← Tela de login / cadastro
│   └── app.html            ← Shell da SPA (Single Page App)
└── static/
    ├── css/app.css
    ├── js/app.js
    └── uploads/            ← Imagens enviadas pelos usuários
```

## Como rodar

```bash
pip install -r requirements.txt
python app.py
# Acesse: http://localhost:5000
```

## Usuários demo

| Usuário       | Senha  | Curso          |
|---------------|--------|----------------|
| joao.silva    | 123456 | Informática    |
| maria.santos  | 123456 | Administração  |
| pedro.alves   | 123456 | Eletrônica     |

## Funcionalidades v2

### Social
- ✅ Feed personalizado (posts de quem você segue)
- ✅ Stories com duração de 24h e barra de progresso
- ✅ Posts com texto e/ou fotos
- ✅ Curtir e comentar publicações
- ✅ Explorar todas as publicações e pessoas

### Perfil
- ✅ Editar nome, bio e turma
- ✅ Trocar foto de perfil (upload de imagem)
- ✅ Contador de posts, seguidores e seguindo
- ✅ Seguir / deixar de seguir

### Mensagens Diretas (DM)
- ✅ Conversar com qualquer aluno pelo perfil dele
- ✅ Lista de conversas com última mensagem
- ✅ Interface de chat em tempo real (dentro da sessão)

### Hub do Curso
- ✅ Aba exclusiva para o curso do aluno (Informática, Administração, etc.)
- ✅ Vagas de estágio com empresa, descrição e prazo
- ✅ Avisos de provas com disciplina e data
- ✅ Fórum de dúvidas com respostas e marcação "resolvido"

### Notificações
- ✅ Curtidas, comentários, novos seguidores e mensagens
- ✅ Badge de contagem não lida

## Próximos passos

- Banco de dados real (SQLite/PostgreSQL com SQLAlchemy)
- Hash de senhas com bcrypt
- WebSockets para chat em tempo real
- Deploy no Railway ou Render (gratuito)
- PWA para instalar no celular
