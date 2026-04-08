"""
FaeNet v5 — Moderadores, Admin, Denúncias, Tipo de conta (aluno/professor)
"""
import os, uuid, base64, json
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, and_, func
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "faenet_secret_dev_2025")

db_url = os.environ.get("DATABASE_URL", "sqlite:///faenet.db")
if db_url.startswith("postgres://"): db_url = db_url.replace("postgres://","postgresql://",1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# ── Roles ──────────────────────────────────────────────────────────
ROLE_USER  = "user"
ROLE_MOD   = "mod"
ROLE_ADMIN = "admin"

def time_ago(ts):
    try:
        if isinstance(ts, str): ts = datetime.fromisoformat(ts)
        if ts and ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
        diff = (datetime.now(timezone.utc) - ts).total_seconds()
        if diff < 60: return "agora mesmo"
        if diff < 3600: return f"há {int(diff//60)} min"
        if diff < 86400: return f"há {int(diff//3600)}h"
        return f"há {int(diff//86400)}d"
    except: return "recentemente"

def save_b64(b64_data):
    try:
        if not b64_data: return None
        if "," in b64_data: header, data = b64_data.split(",",1)
        else: header, data = "", b64_data
        ext = "jpg"
        if "png" in header: ext = "png"
        elif "gif" in header: ext = "gif"
        elif "webp" in header: ext = "webp"
        fname = f"{uuid.uuid4().hex}.{ext}"
        with open(os.path.join(UPLOAD_FOLDER, fname), "wb") as f:
            f.write(base64.b64decode(data))
        return f"/static/uploads/{fname}"
    except: return None

def require_auth(): return session.get("username")
def require_mod():
    me = session.get("username")
    if not me: return None
    u = User.query.get(me)
    return me if u and u.role in (ROLE_MOD, ROLE_ADMIN) else None
def require_admin():
    me = session.get("username")
    if not me: return None
    u = User.query.get(me)
    return me if u and u.role == ROLE_ADMIN else None

# ── Association tables ─────────────────────────────────────────────
followers_t = db.Table("followers",
    db.Column("follower", db.String(60), db.ForeignKey("users.username"), primary_key=True),
    db.Column("followed", db.String(60), db.ForeignKey("users.username"), primary_key=True))
post_likes_t = db.Table("post_likes",
    db.Column("username", db.String(60), db.ForeignKey("users.username"), primary_key=True),
    db.Column("post_id",  db.String(24), db.ForeignKey("posts.id"),       primary_key=True))
post_saves_t = db.Table("post_saves",
    db.Column("username", db.String(60), db.ForeignKey("users.username"), primary_key=True),
    db.Column("post_id",  db.String(24), db.ForeignKey("posts.id"),       primary_key=True))
post_reposts_t = db.Table("post_reposts",
    db.Column("username", db.String(60), db.ForeignKey("users.username"), primary_key=True),
    db.Column("post_id",  db.String(24), db.ForeignKey("posts.id"),       primary_key=True))
story_viewers_t = db.Table("story_viewers",
    db.Column("username", db.String(60), db.ForeignKey("users.username"), primary_key=True),
    db.Column("story_id", db.String(24), db.ForeignKey("stories.id"),     primary_key=True))

# ── Models ─────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"
    username      = db.Column(db.String(60), primary_key=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name          = db.Column(db.String(120), nullable=False)
    curso         = db.Column(db.String(80),  default="")
    turma         = db.Column(db.String(100), default="")
    avatar_text   = db.Column(db.String(4),   default="?")
    avatar_img    = db.Column(db.Text,        nullable=True)
    banner_img    = db.Column(db.Text,        nullable=True)
    bio           = db.Column(db.String(300), default="")
    online        = db.Column(db.Boolean,     default=False)
    last_seen     = db.Column(db.DateTime,    default=datetime.utcnow)
    joined        = db.Column(db.DateTime,    default=datetime.utcnow)
    # Novos campos v5
    role          = db.Column(db.String(10),  default=ROLE_USER)   # user | mod | admin
    account_type  = db.Column(db.String(10),  default="aluno")     # aluno | professor
    matricula     = db.Column(db.String(30),  nullable=True)       # alunos
    professor_id  = db.Column(db.String(30),  nullable=True)       # professores
    banned        = db.Column(db.Boolean,     default=False)
    warned        = db.Column(db.Boolean,     default=False)

    following = db.relationship("User", secondary=followers_t,
        primaryjoin=(followers_t.c.follower == username),
        secondaryjoin=(followers_t.c.followed == username),
        backref="followers")

    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)

    def to_dict(self):
        fl = [f.username for f in self.followers]
        fw = [f.username for f in self.following]
        return {
            "username": self.username, "name": self.name,
            "curso": self.curso, "turma": self.turma,
            "avatar_text": self.avatar_text, "avatar_img": self.avatar_img,
            "banner_img": self.banner_img, "bio": self.bio,
            "online": self.online,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "joined": self.joined.strftime("%Y-%m-%d") if self.joined else None,
            "followers_count": len(fl), "following_count": len(fw),
            "followers": fl, "following": fw,
            "role": self.role,
            "account_type": self.account_type,
            "banned": self.banned, "warned": self.warned,
        }


class Post(db.Model):
    __tablename__ = "posts"
    id        = db.Column(db.String(24), primary_key=True, default=lambda: f"p{uuid.uuid4().hex[:12]}")
    username  = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    content   = db.Column(db.Text, default="")
    images    = db.Column(db.Text, default="[]")
    poll_data = db.Column(db.Text, nullable=True)
    repost_of = db.Column(db.String(24), db.ForeignKey("posts.id"), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    author    = db.relationship("User", foreign_keys=[username], backref="posts")
    original  = db.relationship("Post", remote_side="Post.id", foreign_keys=[repost_of])
    comments  = db.relationship("Comment", backref="post", cascade="all,delete-orphan")
    likers    = db.relationship("User", secondary=post_likes_t,   backref="liked_posts")
    savers    = db.relationship("User", secondary=post_saves_t,   backref="saved_posts")
    reposters = db.relationship("User", secondary=post_reposts_t, backref="reposted_posts")

    def to_dict(self, me=None):
        u = self.author; imgs = json.loads(self.images or "[]")
        poll = None
        if self.poll_data:
            poll = json.loads(self.poll_data)
            total = sum(len(v) for v in poll.get("votes", {}).values())
            poll["total"] = total
            poll["voted"] = next((opt for opt,vs in poll["votes"].items() if me and me in vs), None)
        ri = None
        if self.repost_of and self.original:
            orig = self.original; oa = orig.author
            ri = {"id": orig.id, "username": orig.username,
                  "name": oa.name if oa else "?", "avatar_text": oa.avatar_text if oa else "?",
                  "avatar_img": oa.avatar_img if oa else None,
                  "content": orig.content, "images": json.loads(orig.images or "[]"),
                  "time": time_ago(orig.timestamp)}
        lk = [x.username for x in self.likers]
        sv = [x.username for x in self.savers]
        rp = [x.username for x in self.reposters]
        reports = Report.query.filter_by(post_id=self.id).count()
        return {
            "id": self.id, "username": self.username,
            "name": u.name if u else "?",
            "avatar_text": u.avatar_text if u else "?",
            "avatar_img": u.avatar_img if u else None,
            "role": u.role if u else ROLE_USER,
            "turma": u.turma if u else "",
            "content": self.content, "images": imgs, "poll": poll, "repost_of": ri,
            "likes": lk, "liked": (me in lk) if me else False, "like_count": len(lk),
            "saved": (me in sv) if me else False, "save_count": len(sv),
            "reposted": (me in rp) if me else False, "repost_count": len(rp),
            "comments": [c.to_dict() for c in sorted(self.comments, key=lambda x: x.timestamp or datetime.min)],
            "timestamp": self.timestamp.isoformat() if self.timestamp else "",
            "time": time_ago(self.timestamp),
            "report_count": reports,
        }


class Comment(db.Model):
    __tablename__ = "comments"
    id        = db.Column(db.String(24), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    post_id   = db.Column(db.String(24), db.ForeignKey("posts.id"), nullable=False)
    username  = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    text      = db.Column(db.Text, nullable=False)
    reply_to  = db.Column(db.String(24), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    author    = db.relationship("User", lazy="joined")
    def to_dict(self):
        u = self.author
        return {"id": self.id, "post_id": self.post_id, "username": self.username,
                "user": u.name if u else "?",
                "avatar_text": u.avatar_text if u else "?", "avatar_img": u.avatar_img if u else None,
                "text": self.text, "reply_to": self.reply_to,
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "time": time_ago(self.timestamp)}


class Story(db.Model):
    __tablename__ = "stories"
    id        = db.Column(db.String(24), primary_key=True, default=lambda: f"s{uuid.uuid4().hex[:12]}")
    username  = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    image     = db.Column(db.Text, nullable=False)
    caption   = db.Column(db.String(200), default="")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    author    = db.relationship("User", foreign_keys=[username], backref="stories")
    viewers   = db.relationship("User", secondary=story_viewers_t)
    def to_dict(self, me=None):
        u = self.author; vlist = [v.username for v in self.viewers]
        return {"id": self.id, "username": self.username,
                "name": u.name if u else "?",
                "avatar_text": u.avatar_text if u else "?", "avatar_img": u.avatar_img if u else None,
                "image": self.image, "caption": self.caption, "viewers": vlist,
                "seen": (me in vlist) if me else False,
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "time": time_ago(self.timestamp)}


class Message(db.Model):
    __tablename__ = "messages"
    id        = db.Column(db.String(24), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    from_user = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    to_user   = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    text      = db.Column(db.Text, default="")
    file_url  = db.Column(db.Text, nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(20), nullable=True)
    reply_to  = db.Column(db.Text, nullable=True)
    read      = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    def to_dict(self):
        return {"id": self.id, "from": self.from_user, "to": self.to_user,
                "text": self.text, "file_url": self.file_url,
                "file_name": self.file_name, "file_type": self.file_type,
                "reply_to": json.loads(self.reply_to) if self.reply_to else None,
                "read": self.read,
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "time": time_ago(self.timestamp)}


class Notification(db.Model):
    __tablename__ = "notifications"
    id               = db.Column(db.String(24), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    to_user          = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    from_name        = db.Column(db.String(120), nullable=False)
    from_avatar_text = db.Column(db.String(4), default="?")
    from_avatar_img  = db.Column(db.Text, nullable=True)
    notif_type       = db.Column(db.String(30), nullable=False)
    text             = db.Column(db.String(200), nullable=False)
    read             = db.Column(db.Boolean, default=False)
    timestamp        = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    def to_dict(self):
        return {"id": self.id, "type": self.notif_type, "from": self.from_name,
                "avatar_text": self.from_avatar_text, "avatar_img": self.from_avatar_img,
                "text": self.text, "read": self.read,
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "time": time_ago(self.timestamp)}


class HubItem(db.Model):
    __tablename__ = "hub_items"
    id        = db.Column(db.String(24), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    curso     = db.Column(db.String(80), nullable=False, index=True)
    item_type = db.Column(db.String(20), nullable=False)
    parent_id = db.Column(db.String(24), nullable=True)
    username  = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    title     = db.Column(db.String(200), default="")
    content   = db.Column(db.Text, default="")
    extra     = db.Column(db.Text, default="{}")
    solved    = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    author    = db.relationship("User", lazy="joined")
    def to_dict(self):
        ex = json.loads(self.extra or "{}"); u = self.author
        base = {"id": self.id, "curso": self.curso, "type": self.item_type,
                "username": self.username,
                "name": u.name if u else "?",
                "avatar_text": u.avatar_text if u else "?", "avatar_img": u.avatar_img if u else None,
                "title": self.title, "content": self.content, "solved": self.solved,
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "time": time_ago(self.timestamp)}
        base.update(ex); return base


class Report(db.Model):
    """Denúncias de posts feitas por usuários."""
    __tablename__ = "reports"
    id        = db.Column(db.String(24), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    post_id   = db.Column(db.String(24), db.ForeignKey("posts.id"), nullable=False)
    reporter  = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    reason    = db.Column(db.String(200), default="")
    status    = db.Column(db.String(20), default="pending")  # pending | resolved | ignored
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    post      = db.relationship("Post", backref="reports")
    def to_dict(self):
        p = self.post; u = User.query.get(self.reporter)
        return {"id": self.id, "post_id": self.post_id,
                "post_content": p.content[:80] if p else "",
                "post_author": p.username if p else "",
                "reporter": self.reporter,
                "reporter_name": u.name if u else "?",
                "reason": self.reason, "status": self.status,
                "total_reports": Report.query.filter_by(post_id=self.post_id).count(),
                "timestamp": self.timestamp.isoformat() if self.timestamp else "",
                "time": time_ago(self.timestamp)}


# ── Seed ───────────────────────────────────────────────────────────
def seed_db():
    if User.query.count() > 0: return
    # Admin fixo
    admin = User(username="admin", name="Administrador FaeNet",
                 curso="Administração", turma="Administração",
                 avatar_text="AD", bio="Administrador da rede.", role=ROLE_ADMIN,
                 account_type="professor", professor_id="ADMIN001")
    admin.set_password("admin123"); db.session.add(admin)

    users_data = [
        ("joao.silva",   "123456", "João Silva",   "Informática",   "3º Ano - Informática",   "JS", "Apaixonado por tecnologia 🚀",  "aluno",    "20240001", None),
        ("maria.santos", "123456", "Maria Santos", "Administração", "2º Ano - Administração", "MS", "Estudante dedicada 📚✨",        "aluno",    "20240002", None),
        ("pedro.alves",  "123456", "Pedro Alves",  "Eletrônica",    "1º Ano - Eletrônica",    "PA", "Eletricidade é vida ⚡",         "aluno",    "20240003", None),
        ("prof.carlos",  "123456", "Prof. Carlos", "Informática",   "Professor",              "PC", "Professor de Redes.",           "professor", None,      "PROF001"),
    ]
    us = {}
    for un,pw,name,curso,turma,ini,bio,atype,mat,pid in users_data:
        u = User(username=un, name=name, curso=curso, turma=turma,
                 avatar_text=ini, bio=bio, account_type=atype,
                 matricula=mat, professor_id=pid)
        u.set_password(pw); db.session.add(u); us[un] = u
    db.session.flush()

    us["joao.silva"].following.append(us["maria.santos"])
    us["joao.silva"].following.append(us["pedro.alves"])
    us["maria.santos"].following.append(us["joao.silva"])
    us["pedro.alves"].following.append(us["maria.santos"])

    p1 = Post(id="p1", username="maria.santos", content="Acabei de terminar o TCC! 🎉", timestamp=datetime(2024,6,10,14,0,0))
    p2 = Post(id="p2", username="pedro.alves",  content="Aula de laboratório hoje foi demais! ⚡🔌", timestamp=datetime(2024,6,10,11,0,0))
    p3 = Post(id="p3", username="joao.silva",   content="Alguém tem material sobre algoritmos de ordenação? 📖💻", timestamp=datetime(2024,6,10,8,0,0))
    for p in [p1,p2,p3]: db.session.add(p)
    db.session.flush()
    p1.likers.append(us["joao.silva"]); p1.likers.append(us["pedro.alves"])
    p3.likers.append(us["maria.santos"]); p3.likers.append(us["pedro.alves"])

    db.session.add_all([
        Comment(post_id="p1", username="joao.silva",   text="Parabéns! Ficou incrível!", timestamp=datetime(2024,6,10,14,30,0)),
        Comment(post_id="p3", username="maria.santos", text="Te mando no privado!",       timestamp=datetime(2024,6,10,9,0,0)),
        Notification(to_user="joao.silva", from_name="Maria Santos", from_avatar_text="MS", notif_type="like",   text="curtiu sua publicação", timestamp=datetime(2024,6,10,15,0,0)),
        Notification(to_user="joao.silva", from_name="Pedro Alves",  from_avatar_text="PA", notif_type="follow", text="começou a te seguir",    timestamp=datetime(2024,6,10,13,0,0)),
        HubItem(curso="Informática",   item_type="estagio",     username="prof.carlos", title="Estágio TI — TechRio",       content="Vaga para desenvolvimento web.",   extra=json.dumps({"company":"TechRio Soluções","deadline":"2024-07-15","link":"#"})),
        HubItem(curso="Informática",   item_type="prova",       username="prof.carlos", title="Prova de Redes",              content="Modelo OSI, TCP/IP, IPv4.",        extra=json.dumps({"subject":"Redes de Computadores","date":"2024-06-21"})),
        HubItem(id="ft1", curso="Informática", item_type="forum_topic", username="pedro.alves", title="Como entender ponteiros em C?", content="Tô quebrando a cabeça com ponteiros!", extra=json.dumps({"tags":["C","ponteiros"]}), solved=True),
        HubItem(curso="Informática",   item_type="forum_answer", username="joao.silva",  parent_id="ft1", content="Ponteiro guarda o endereço de memória. int x=5; int *p=&x;", extra=json.dumps({"likes":[]})),
        HubItem(curso="Administração", item_type="estagio",     username="admin",        title="Estágio Administrativo — Caixa", content="Auxiliar administrativo.",     extra=json.dumps({"company":"Caixa Econômica Federal","deadline":"2024-07-20","link":"#"})),
        HubItem(curso="Administração", item_type="prova",       username="admin",        title="Prova de Contabilidade",         content="Balanço patrimonial, DRE.",     extra=json.dumps({"subject":"Contabilidade Geral","date":"2024-06-25"})),
        HubItem(curso="Eletrônica",    item_type="prova",       username="prof.carlos",  title="Prova de Circuitos",             content="Leis de Kirchhoff, RC, RL, RLC.", extra=json.dumps({"subject":"Circuitos Elétricos","date":"2024-06-24"})),
        HubItem(curso="Eletrônica",    item_type="forum_topic", username="pedro.alves",  title="Dúvida sobre transformadores",   content="Qual a diferença entre step-up e step-down?", extra=json.dumps({"tags":["eletromagnetismo"]})),
        # Exemplo de denúncia
        Report(post_id="p2", reporter="joao.silva", reason="Conteúdo inadequado"),
    ])
    db.session.commit()
    print("✅ DB seeded v5.")


# ── Page routes ────────────────────────────────────────────────────
@app.route("/")
def index():
    if "username" in session: return redirect("/feed")
    return render_template("login.html")

@app.route("/feed")
@app.route("/profile")
@app.route("/profile/<path:u>")
@app.route("/messages")
@app.route("/messages/<path:u>")
@app.route("/hub")
@app.route("/modpanel")
def spa(**kw):
    if "username" not in session: return redirect("/")
    u = User.query.get(session["username"])
    if not u: session.pop("username", None); return redirect("/")
    return render_template("app.html", user=u.to_dict())

# ── Auth ───────────────────────────────────────────────────────────
@app.route("/login", methods=["POST"])
def login():
    d = request.get_json(); uname = d.get("username","").lower().strip()
    u = User.query.get(uname)
    if not u or not u.check_password(d.get("password","")):
        return jsonify({"success": False, "error": "Usuário ou senha incorretos"}), 401
    if u.banned:
        return jsonify({"success": False, "error": "Sua conta foi banida. Entre em contato com a administração."}), 403
    session["username"] = uname
    u.online = True; u.last_seen = datetime.utcnow(); db.session.commit()
    return jsonify({"success": True, "role": u.role})

@app.route("/register", methods=["POST"])
def register():
    d = request.get_json(); uname = d.get("username","").lower().strip()
    if not uname or User.query.get(uname):
        return jsonify({"success": False, "error": "Usuário já existe"}), 400
    atype = d.get("account_type", "aluno")
    mat   = d.get("matricula","").strip()
    pid   = d.get("professor_id","").strip()
    # Validação simples de ID
    if atype == "aluno" and not mat:
        return jsonify({"success": False, "error": "Informe o número de matrícula"}), 400
    if atype == "professor" and not pid:
        return jsonify({"success": False, "error": "Informe o ID do professor"}), 400
    name = d.get("name",""); ini = "".join([w[0].upper() for w in name.split()[:2]])
    curso = d.get("curso",""); ano = d.get("turma_num","1º Ano")
    turma = f"{ano} - {curso}" if atype == "aluno" else "Professor"
    u = User(username=uname, name=name, curso=curso, turma=turma,
             avatar_text=ini, bio="", account_type=atype,
             matricula=mat if atype=="aluno" else None,
             professor_id=pid if atype=="professor" else None)
    u.set_password(d.get("password",""))
    db.session.add(u); db.session.commit()
    session["username"] = uname
    return jsonify({"success": True})

@app.route("/logout")
def logout():
    me = session.get("username")
    if me:
        u = User.query.get(me)
        if u: u.online = False; u.last_seen = datetime.utcnow(); db.session.commit()
    session.pop("username", None); return redirect("/")

# ── API: Me ────────────────────────────────────────────────────────
@app.route("/api/me")
def api_me():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    return jsonify(User.query.get(me).to_dict())

@app.route("/api/me/edit", methods=["POST"])
def api_edit_profile():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json(); u = User.query.get(me)
    if d.get("name","").strip():
        u.name = d["name"].strip()
        u.avatar_text = "".join([w[0].upper() for w in u.name.split()[:2]])
    if "bio"   in d: u.bio = d["bio"][:200]
    if "turma" in d and d["turma"].strip(): u.turma = d["turma"].strip()
    if d.get("avatar_img"):
        url = save_b64(d["avatar_img"])
        if url: u.avatar_img = url
    if d.get("banner_img"):
        url = save_b64(d["banner_img"])
        if url: u.banner_img = url
    db.session.commit(); return jsonify(u.to_dict())

@app.route("/api/me/online", methods=["POST"])
def set_online():
    me = require_auth()
    if not me: return jsonify({}), 401
    u = User.query.get(me)
    if u: u.online = True; u.last_seen = datetime.utcnow(); db.session.commit()
    return jsonify({"ok": True})

# ── API: Posts ─────────────────────────────────────────────────────
@app.route("/api/posts")
def api_posts():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    user = User.query.get(me)
    fn = [f.username for f in user.following] + [me]
    posts = Post.query.filter(Post.username.in_(fn)).order_by(Post.timestamp.desc()).all()
    return jsonify([p.to_dict(me) for p in posts])

@app.route("/api/posts/all")
def api_posts_all():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    return jsonify([p.to_dict(me) for p in Post.query.order_by(Post.timestamp.desc()).all()])

@app.route("/api/posts/user/<username>")
def api_user_posts(username):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    return jsonify([p.to_dict(me) for p in Post.query.filter_by(username=username).order_by(Post.timestamp.desc()).all()])

@app.route("/api/posts/saved")
def api_saved_posts():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    user = User.query.get(me)
    return jsonify([p.to_dict(me) for p in user.saved_posts])

@app.route("/api/posts", methods=["POST"])
def create_post():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json(); content = d.get("content","").strip()
    images = [url for url in [save_b64(b) for b in d.get("images",[])] if url]
    poll = None
    if d.get("poll"):
        opts = d["poll"].get("options",[]); q = d["poll"].get("question","")
        if q and len(opts) >= 2:
            poll = {"question": q, "options": opts, "votes": {o:[] for o in opts}}
    if not content and not images and not poll: return jsonify({"error":"Vazio"}), 400
    post = Post(username=me, content=content, images=json.dumps(images),
                poll_data=json.dumps(poll) if poll else None)
    db.session.add(post); db.session.commit()
    check_badges(me)
    sse_push(me, "new_post", {"id": post.id})
    return jsonify(post.to_dict(me)), 201

@app.route("/api/posts/<pid>/like", methods=["POST"])
def toggle_like(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid); user = User.query.get(me)
    if not p: return jsonify({"error":"Não encontrado"}), 404
    if user in p.likers: p.likers.remove(user); liked = False
    else:
        p.likers.append(user); liked = True
        if p.username != me:
            db.session.add(Notification(to_user=p.username, from_name=user.name,
                from_avatar_text=user.avatar_text, from_avatar_img=user.avatar_img,
                notif_type="like", text="curtiu sua publicação"))
    db.session.commit()
    if liked and p.username != me:
        sse_push(p.username, "notification", {"type":"like","text":f"{user.name} curtiu sua publicação","from":me})
    return jsonify({"liked": liked, "count": len(p.likers)})

@app.route("/api/posts/<pid>/save", methods=["POST"])
def toggle_save(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid); user = User.query.get(me)
    if not p: return jsonify({"error":"Não encontrado"}), 404
    if user in p.savers: p.savers.remove(user); saved = False
    else: p.savers.append(user); saved = True
    db.session.commit()
    return jsonify({"saved": saved, "count": len(p.savers)})

@app.route("/api/posts/<pid>/repost", methods=["POST"])
def toggle_repost(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid); user = User.query.get(me)
    if not p: return jsonify({"error":"Não encontrado"}), 404
    if user in p.reposters:
        p.reposters.remove(user)
        Post.query.filter_by(username=me, repost_of=pid).delete()
        reposted = False
    else:
        p.reposters.append(user)
        rp = Post(username=me, content="", images="[]", repost_of=pid)
        db.session.add(rp); reposted = True
    db.session.commit()
    return jsonify({"reposted": reposted, "count": len(p.reposters)})

@app.route("/api/posts/<pid>/poll/vote", methods=["POST"])
def vote_poll(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid)
    if not p or not p.poll_data: return jsonify({"error":"Não encontrado"}), 404
    poll = json.loads(p.poll_data); opt = request.get_json().get("option")
    for vs in poll["votes"].values():
        if me in vs: vs.remove(me)
    if opt in poll["votes"]: poll["votes"][opt].append(me)
    p.poll_data = json.dumps(poll); db.session.commit()
    total = sum(len(v) for v in poll["votes"].values())
    return jsonify({"votes": poll["votes"], "total": total, "voted": opt})

@app.route("/api/posts/<pid>/delete", methods=["POST"])
def delete_post(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid)
    if not p: return jsonify({"error":"Não encontrado"}), 404
    u = User.query.get(me)
    # dono ou moderador/admin podem apagar
    if p.username != me and u.role not in (ROLE_MOD, ROLE_ADMIN):
        return jsonify({"error":"Não autorizado"}), 403
    db.session.delete(p); db.session.commit()
    return jsonify({"ok": True})

@app.route("/api/posts/<pid>/comment", methods=["POST"])
def add_comment(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid); user = User.query.get(me)
    if not p: return jsonify({"error":"Não encontrado"}), 404
    d = request.get_json()
    c = Comment(post_id=pid, username=me, text=d.get("text",""), reply_to=d.get("reply_to"))
    db.session.add(c)
    if p.username != me:
        db.session.add(Notification(to_user=p.username, from_name=user.name,
            from_avatar_text=user.avatar_text, from_avatar_img=user.avatar_img,
            notif_type="comment", text="comentou na sua publicação"))
    db.session.commit(); return jsonify(c.to_dict()), 201

# ── API: Denúncias ─────────────────────────────────────────────────
@app.route("/api/posts/<pid>/report", methods=["POST"])
def report_post(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid)
    if not p: return jsonify({"error":"Não encontrado"}), 404
    # Evitar dupla denúncia do mesmo usuário
    existing = Report.query.filter_by(post_id=pid, reporter=me).first()
    if existing: return jsonify({"error":"Você já denunciou este post"}), 400
    d = request.get_json()
    r = Report(post_id=pid, reporter=me, reason=d.get("reason","Conteúdo inadequado"))
    db.session.add(r); db.session.commit()
    return jsonify({"ok": True})

# ── API: Stories ───────────────────────────────────────────────────
@app.route("/api/stories")
def api_stories():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    user = User.query.get(me)
    fn = [f.username for f in user.following] + [me]
    cutoff = datetime.utcnow() - timedelta(hours=24)
    stories = Story.query.filter(Story.username.in_(fn), Story.timestamp >= cutoff).order_by(Story.timestamp.desc()).all()
    groups = {}
    for s in stories:
        sd = s.to_dict(me)
        if s.username not in groups:
            ua = s.author
            groups[s.username] = {"username": s.username, "name": ua.name,
                "avatar_text": ua.avatar_text, "avatar_img": ua.avatar_img,
                "stories": [], "has_unseen": False}
        if not sd["seen"]: groups[s.username]["has_unseen"] = True
        groups[s.username]["stories"].append(sd)
    return jsonify(list(groups.values()))

@app.route("/api/stories", methods=["POST"])
def create_story():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json(); url = save_b64(d.get("image",""))
    if not url: return jsonify({"error":"Erro ao salvar"}), 500
    s = Story(username=me, image=url, caption=d.get("caption",""))
    db.session.add(s); db.session.commit()
    check_badges(me)
    return jsonify(s.to_dict(me)), 201

@app.route("/api/stories/<sid>/view", methods=["POST"])
def view_story(sid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    s = Story.query.get(sid); user = User.query.get(me)
    if s and user not in s.viewers: s.viewers.append(user); db.session.commit()
    return jsonify({"ok": True})

@app.route("/api/stories/<sid>/delete", methods=["POST"])
def delete_story(sid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    s = Story.query.get(sid)
    if not s: return jsonify({"error":"Não encontrado"}), 404
    u = User.query.get(me)
    if s.username != me and u.role not in (ROLE_MOD, ROLE_ADMIN):
        return jsonify({"error":"Não autorizado"}), 403
    db.session.delete(s); db.session.commit()
    return jsonify({"ok": True})

# ── API: Messages ──────────────────────────────────────────────────
@app.route("/api/conversations")
def api_conversations():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    all_msgs = Message.query.filter(or_(Message.from_user==me, Message.to_user==me)).all()
    others = set(m.to_user if m.from_user==me else m.from_user for m in all_msgs)
    convos = []
    for other in others:
        ou = User.query.get(other)
        if not ou: continue
        last = Message.query.filter(
            or_(and_(Message.from_user==me, Message.to_user==other),
                and_(Message.from_user==other, Message.to_user==me))
        ).order_by(Message.timestamp.desc()).first()
        unread = Message.query.filter_by(from_user=other, to_user=me, read=False).count()
        lt = last.text if last and last.text else ("📎 Arquivo" if last and last.file_url else "")
        convos.append({"with": other, "name": ou.name, "avatar_text": ou.avatar_text,
            "avatar_img": ou.avatar_img, "online": ou.online,
            "last_message": lt, "last_time": time_ago(last.timestamp) if last else "", "unread": unread})
    return jsonify(convos)

@app.route("/api/messages/<other>")
def api_get_messages(other):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    msgs = Message.query.filter(
        or_(and_(Message.from_user==me, Message.to_user==other),
            and_(Message.from_user==other, Message.to_user==me))
    ).order_by(Message.timestamp).all()
    for m in msgs:
        if m.from_user != me and not m.read: m.read = True
    db.session.commit()
    return jsonify([m.to_dict() for m in msgs])

@app.route("/api/messages/<other>", methods=["POST"])
def api_send_message(other):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    if not User.query.get(other): return jsonify({"error":"Usuário não encontrado"}), 404
    d = request.get_json(); user = User.query.get(me)
    text = d.get("text","").strip(); file_url = file_name = file_type = None
    if d.get("file_b64"):
        file_url = save_b64(d["file_b64"]); file_name = d.get("file_name","arquivo"); file_type = "file"
    if d.get("image_b64"):
        file_url = save_b64(d["image_b64"]); file_type = "image"; file_name = "imagem"
    if not text and not file_url: return jsonify({"error":"Vazio"}), 400
    rt = d.get("reply_to")
    msg = Message(from_user=me, to_user=other, text=text, file_url=file_url,
                  file_name=file_name, file_type=file_type,
                  reply_to=json.dumps(rt) if rt else None)
    notif = Notification(to_user=other, from_name=user.name,
        from_avatar_text=user.avatar_text, from_avatar_img=user.avatar_img,
        notif_type="message", text="enviou uma mensagem para você")
    db.session.add(msg); db.session.add(notif); db.session.commit()
    sse_push(other, "notification", {"type":"message","text":f"{user.name} enviou uma mensagem","from":me})
    sse_push(other, "new_message", {"from":me,"text":text[:40]})
    return jsonify(msg.to_dict()), 201

# ── API: Users ─────────────────────────────────────────────────────
@app.route("/api/users/search")
def search_users():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    q = request.args.get("q","").strip()
    if q:
        users = User.query.filter(or_(User.name.ilike(f"%{q}%"), User.username.ilike(f"%{q}%"))).limit(20).all()
    else:
        users = User.query.limit(30).all()
    return jsonify([u.to_dict() for u in users])

@app.route("/api/users/<username>")
def api_get_user(username):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    u = User.query.get(username)
    if not u: return jsonify({"error":"Não encontrado"}), 404
    return jsonify(u.to_dict())

@app.route("/api/users/<username>/follow", methods=["POST"])
def follow_user(username):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    if me == username: return jsonify({"error":"Inválido"}), 400
    mu = User.query.get(me); tu = User.query.get(username)
    if not tu: return jsonify({"error":"Não encontrado"}), 404
    if tu in mu.following:
        mu.following.remove(tu); following = False
    else:
        mu.following.append(tu); following = True
        db.session.add(Notification(to_user=username, from_name=mu.name,
            from_avatar_text=mu.avatar_text, from_avatar_img=mu.avatar_img,
            notif_type="follow", text="começou a te seguir"))
    db.session.commit()
    if following: check_badges(username)
    return jsonify({"following": following, "followers_count": len(tu.followers)})

@app.route("/api/users/suggestions")
def user_suggestions():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    user = User.query.get(me)
    fn = [f.username for f in user.following] + [me]
    others = User.query.filter(~User.username.in_(fn)).limit(6).all()
    return jsonify([u.to_dict() for u in others])

# ── API: Notifications ─────────────────────────────────────────────
@app.route("/api/notifications")
def api_notifications():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    notifs = Notification.query.filter_by(to_user=me).order_by(Notification.timestamp.desc()).limit(50).all()
    return jsonify([n.to_dict() for n in notifs])

@app.route("/api/notifications/read", methods=["POST"])
def mark_notifs_read():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    Notification.query.filter_by(to_user=me, read=False).update({"read": True})
    db.session.commit(); return jsonify({"ok": True})

# ── API: Hub ───────────────────────────────────────────────────────
def hub_to_json(curso):
    items = HubItem.query.filter_by(curso=curso).order_by(HubItem.timestamp.desc()).all()
    estagios = []; provas = []; tm = {}; am = {}
    for i in items:
        d = i.to_dict()
        if   i.item_type == "estagio":      estagios.append(d)
        elif i.item_type == "prova":        provas.append(d)
        elif i.item_type == "forum_topic":  tm[i.id] = {**d, "answers": []}
        elif i.item_type == "forum_answer": am.setdefault(i.parent_id, []).append(d)
    for tid, ans in am.items():
        if tid in tm: tm[tid]["answers"] = ans
    return {"estagios": estagios, "provas": provas, "forum": list(tm.values())}

@app.route("/api/hub/<curso>")
def api_hub(curso):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    return jsonify(hub_to_json(curso))

@app.route("/api/hub/<curso>/estagios", methods=["POST"])
def create_estagio(curso):
    me = require_mod()
    if not me: return jsonify({"error":"Apenas moderadores podem publicar vagas"}), 403
    d = request.get_json()
    i = HubItem(curso=curso, item_type="estagio", username=me,
                title=d.get("title",""), content=d.get("description",""),
                extra=json.dumps({"company":d.get("company",""),"deadline":d.get("deadline",""),"link":d.get("link","#")}))
    db.session.add(i); db.session.commit(); return jsonify(i.to_dict()), 201

@app.route("/api/hub/<curso>/provas", methods=["POST"])
def create_prova(curso):
    me = require_mod()
    if not me: return jsonify({"error":"Apenas moderadores podem publicar avisos de provas"}), 403
    d = request.get_json()
    i = HubItem(curso=curso, item_type="prova", username=me,
                title=d.get("title",""), content=d.get("description",""),
                extra=json.dumps({"subject":d.get("subject",""),"date":d.get("date","")}))
    db.session.add(i); db.session.commit(); return jsonify(i.to_dict()), 201

@app.route("/api/hub/<curso>/forum", methods=["POST"])
def create_forum_topic(curso):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json()
    i = HubItem(curso=curso, item_type="forum_topic", username=me,
                title=d.get("title",""), content=d.get("content",""),
                extra=json.dumps({"tags":d.get("tags",[])}))
    db.session.add(i); db.session.commit()
    return jsonify({**i.to_dict(), "answers": []}), 201

@app.route("/api/hub/<curso>/forum/<tid>/answer", methods=["POST"])
def answer_forum(curso, tid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    topic = HubItem.query.get(tid)
    if not topic: return jsonify({"error":"Não encontrado"}), 404
    d = request.get_json()
    a = HubItem(curso=curso, item_type="forum_answer", parent_id=tid,
                username=me, content=d.get("content",""), extra=json.dumps({"likes":[]}))
    if d.get("mark_solved"): topic.solved = True
    db.session.add(a); db.session.commit(); return jsonify(a.to_dict()), 201

@app.route("/api/hub/<curso>/forum/<tid>/solve", methods=["POST"])
def mark_solved(curso, tid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    t = HubItem.query.get(tid)
    if not t: return jsonify({"error":"Não encontrado"}), 404
    if t.username == me: t.solved = not t.solved; db.session.commit()
    return jsonify({"solved": t.solved})

# ══════════════════════════════════════════════════════════════════
# API: PAINEL DE MODERAÇÃO
# ══════════════════════════════════════════════════════════════════

@app.route("/api/mod/dashboard")
def mod_dashboard():
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    total_users    = User.query.count()
    total_posts    = Post.query.count()
    total_comments = Comment.query.count()
    total_reports  = Report.query.filter_by(status="pending").count()
    # Posts mais curtidos
    all_posts = Post.query.all()
    top_posts = sorted(all_posts, key=lambda p: len(p.likers), reverse=True)[:5]
    # Usuários mais ativos (mais posts)
    from sqlalchemy import text
    top_users = db.session.execute(
        db.select(User).join(Post, Post.username == User.username)
        .group_by(User.username).order_by(func.count(Post.id).desc()).limit(5)
    ).scalars().all()
    # Crescimento (usuários por mês últimos 6 meses)
    growth = []
    for i in range(5, -1, -1):
        d = datetime.utcnow() - timedelta(days=30*i)
        month_start = d.replace(day=1, hour=0, minute=0, second=0)
        month_end   = (month_start + timedelta(days=32)).replace(day=1)
        count = User.query.filter(User.joined >= month_start, User.joined < month_end).count()
        growth.append({"month": month_start.strftime("%b/%Y"), "count": count})
    return jsonify({
        "total_users": total_users,
        "total_posts": total_posts,
        "total_comments": total_comments,
        "pending_reports": total_reports,
        "top_posts": [{"id":p.id,"content":p.content[:60],"author":p.username,"likes":len(p.likers)} for p in top_posts],
        "top_users": [{"username":u.username,"name":u.name,"posts":Post.query.filter_by(username=u.username).count()} for u in top_users],
        "growth": growth,
    })

@app.route("/api/mod/users")
def mod_list_users():
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    users = User.query.order_by(User.joined.desc()).all()
    return jsonify([u.to_dict() for u in users])

@app.route("/api/mod/users/<username>/edit", methods=["POST"])
def mod_edit_user(username):
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    u = User.query.get(username)
    if not u: return jsonify({"error":"Não encontrado"}), 404
    d = request.get_json()
    if "name"  in d: u.name  = d["name"]
    if "curso" in d: u.curso = d["curso"]
    if "turma" in d: u.turma = d["turma"]
    if "bio"   in d: u.bio   = d["bio"][:200]
    db.session.commit(); return jsonify(u.to_dict())

@app.route("/api/mod/users/<username>/ban", methods=["POST"])
def mod_ban_user(username):
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    u = User.query.get(username)
    if not u: return jsonify({"error":"Não encontrado"}), 404
    if u.role in (ROLE_MOD, ROLE_ADMIN): return jsonify({"error":"Não é possível banir moderadores"}), 403
    u.banned = not u.banned
    db.session.commit()
    return jsonify({"banned": u.banned})

@app.route("/api/mod/users/<username>/warn", methods=["POST"])
def mod_warn_user(username):
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    u = User.query.get(username)
    if not u: return jsonify({"error":"Não encontrado"}), 404
    u.warned = True
    db.session.add(Notification(to_user=username, from_name="Moderação FaeNet",
        from_avatar_text="MOD", notif_type="warn",
        text="Você recebeu uma advertência da moderação. Por favor, siga as regras da comunidade."))
    db.session.commit(); return jsonify({"ok": True})

@app.route("/api/mod/users/<username>/delete", methods=["POST"])
def mod_delete_user(username):
    me = require_admin()  # apenas admin pode excluir contas
    if not me: return jsonify({"error":"Apenas o administrador pode excluir contas"}), 403
    u = User.query.get(username)
    if not u: return jsonify({"error":"Não encontrado"}), 404
    if u.role == ROLE_ADMIN: return jsonify({"error":"Não é possível excluir o administrador"}), 403
    db.session.delete(u); db.session.commit()
    return jsonify({"ok": True})

@app.route("/api/mod/reports")
def mod_reports():
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    # Agrupa denúncias por post
    posts_reported = db.session.query(Report.post_id, func.count(Report.id).label("total"))\
        .filter(Report.status=="pending").group_by(Report.post_id)\
        .order_by(func.count(Report.id).desc()).all()
    result = []
    for post_id, total in posts_reported:
        p = Post.query.get(post_id)
        if not p: continue
        first_report = Report.query.filter_by(post_id=post_id).first()
        result.append({
            "post_id": post_id,
            "post_content": p.content[:80],
            "post_author": p.username,
            "post_author_name": p.author.name if p.author else "?",
            "total_reports": total,
            "reason": first_report.reason if first_report else "",
            "timestamp": p.timestamp.isoformat() if p.timestamp else "",
            "time": time_ago(p.timestamp),
        })
    return jsonify(result)

@app.route("/api/mod/reports/<post_id>/resolve", methods=["POST"])
def mod_resolve_report(post_id):
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    d = request.get_json(); action = d.get("action","ignore")
    if action == "delete":
        p = Post.query.get(post_id)
        if p: db.session.delete(p)
    elif action == "warn":
        p = Post.query.get(post_id)
        if p:
            u = User.query.get(p.username)
            if u:
                u.warned = True
                db.session.add(Notification(to_user=p.username, from_name="Moderação FaeNet",
                    from_avatar_text="MOD", notif_type="warn",
                    text="Seu post foi sinalizado pela moderação. Advertência registrada."))
    Report.query.filter_by(post_id=post_id).update({"status": "resolved" if action != "ignore" else "ignored"})
    db.session.commit(); return jsonify({"ok": True})

@app.route("/api/mod/posts")
def mod_all_posts():
    me = require_mod()
    if not me: return jsonify({"error":"Forbidden"}), 403
    posts = Post.query.order_by(Post.timestamp.desc()).limit(100).all()
    return jsonify([p.to_dict(me) for p in posts])

# ── API: Admin — Gerenciar moderadores ────────────────────────────
@app.route("/api/admin/set-mod", methods=["POST"])
def admin_set_mod():
    me = require_admin()
    if not me: return jsonify({"error":"Apenas o administrador pode fazer isso"}), 403
    d = request.get_json(); username = d.get("username","")
    u = User.query.get(username)
    if not u: return jsonify({"error":"Usuário não encontrado"}), 404
    if u.role == ROLE_ADMIN: return jsonify({"error":"Não é possível alterar o admin"}), 403
    u.role = ROLE_MOD if u.role != ROLE_MOD else ROLE_USER
    db.session.commit()
    return jsonify({"role": u.role, "username": u.username})

if __name__ == "__main__":
    with app.app_context():
        db.create_all(); seed_db()
    app.run(debug=os.environ.get("FLASK_DEBUG","0")=="1",
            host="0.0.0.0", port=int(os.environ.get("PORT",5000)))

# ══════════════════════════════════════════════════════════════════
# v6: FaeBot, SSE push, Reações, Conquistas, Status, Trending
# ══════════════════════════════════════════════════════════════════
import threading, queue, time as time_mod, re
from collections import Counter

# ── SSE: fila de eventos por usuário ──────────────────────────────
_sse_clients = {}  # username -> list of queues
_sse_lock = threading.Lock()

def sse_push(to_user, event_type, data):
    """Envia evento SSE para um usuário específico."""
    with _sse_lock:
        queues = _sse_clients.get(to_user, [])
        for q in list(queues):
            try: q.put_nowait({"type": event_type, "data": data})
            except: pass

def sse_broadcast(event_type, data):
    """Envia para todos os usuários conectados."""
    with _sse_lock:
        for username, queues in _sse_clients.items():
            for q in list(queues):
                try: q.put_nowait({"type": event_type, "data": data})
                except: pass

@app.route("/api/sse")
def sse_stream():
    me = require_auth()
    if not me: return "Unauthorized", 401
    q = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients.setdefault(me, []).append(q)
    def generate():
        try:
            yield "data: {\"type\":\"connected\"}\n\n"
            while True:
                try:
                    evt = q.get(timeout=25)
                    yield f"data: {json.dumps(evt)}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"  # keep-alive
        except GeneratorExit:
            pass
        finally:
            with _sse_lock:
                lst = _sse_clients.get(me, [])
                if q in lst: lst.remove(q)
                if not lst: _sse_clients.pop(me, None)
    from flask import Response, stream_with_context
    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

# Patch Notification creation to also SSE-push
_orig_notif_add = db.session.add
def _patched_add(obj):
    _orig_notif_add(obj)
    if isinstance(obj, Notification):
        sse_push(obj.to_user, "notification", {"text": obj.text, "type": obj.notif_type})

# ── Modelo: Reações ───────────────────────────────────────────────
class PostReaction(db.Model):
    __tablename__ = "post_reactions"
    id       = db.Column(db.String(24), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    post_id  = db.Column(db.String(24), db.ForeignKey("posts.id"), nullable=False)
    username = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    emoji    = db.Column(db.String(10), nullable=False)
    __table_args__ = (db.UniqueConstraint("post_id","username"),)

# ── Modelo: Conquistas ────────────────────────────────────────────
class Achievement(db.Model):
    __tablename__ = "achievements"
    id         = db.Column(db.String(24), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    username   = db.Column(db.String(60), db.ForeignKey("users.username"), nullable=False)
    badge_key  = db.Column(db.String(40), nullable=False)
    earned_at  = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("username","badge_key"),)
    def to_dict(self):
        info = BADGES.get(self.badge_key, {"label":self.badge_key,"icon":"🏅","desc":""})
        return {"key":self.badge_key,"label":info["label"],"icon":info["icon"],
                "desc":info["desc"],"earned_at":self.earned_at.strftime("%d/%m/%Y") if self.earned_at else ""}

BADGES = {
    "first_post":    {"icon":"✍️",  "label":"Primeiro Post",      "desc":"Criou sua primeira publicação"},
    "10_posts":      {"icon":"📝",  "label":"Escritor",           "desc":"Criou 10 publicações"},
    "50_posts":      {"icon":"📖",  "label":"Cronista",           "desc":"Criou 50 publicações"},
    "10_followers":  {"icon":"🌟",  "label":"Influenciador",      "desc":"Conquistou 10 seguidores"},
    "50_followers":  {"icon":"🚀",  "label":"Popular",            "desc":"Conquistou 50 seguidores"},
    "first_story":   {"icon":"📸",  "label":"Primeiro Story",     "desc":"Publicou seu primeiro story"},
    "10_likes":      {"icon":"❤️",  "label":"Querido",            "desc":"Recebeu 10 curtidas em um post"},
    "helper":        {"icon":"💡",  "label":"Colaborador",        "desc":"Respondeu 5 dúvidas no fórum"},
    "early_bird":    {"icon":"🐦",  "label":"Pioneiro",           "desc":"Um dos primeiros usuários da FaeNet"},
}

def check_badges(username):
    """Verifica e concede conquistas automaticamente."""
    u = User.query.get(username)
    if not u: return
    earned = {a.badge_key for a in Achievement.query.filter_by(username=username).all()}
    new_badges = []
    def grant(key):
        if key not in earned:
            db.session.add(Achievement(username=username, badge_key=key))
            new_badges.append(key)
            sse_push(username, "achievement", {"key":key, **BADGES.get(key,{})})
    # Pioneiro: primeiros 20 usuários
    if User.query.count() <= 20: grant("early_bird")
    # Posts
    pc = Post.query.filter_by(username=username).count()
    if pc >= 1:  grant("first_post")
    if pc >= 10: grant("10_posts")
    if pc >= 50: grant("50_posts")
    # Seguidores
    fc = len(u.followers)
    if fc >= 10: grant("10_followers")
    if fc >= 50: grant("50_followers")
    # Stories
    if Story.query.filter_by(username=username).count() >= 1: grant("first_story")
    # Curtidas recebidas
    posts = Post.query.filter_by(username=username).all()
    max_likes = max((len(p.likers) for p in posts), default=0)
    if max_likes >= 10: grant("10_likes")
    # Fórum
    ans = HubItem.query.filter_by(username=username, item_type="forum_answer").count()
    if ans >= 5: grant("helper")
    if new_badges: db.session.commit()

# ── Modelo: Status do usuário ─────────────────────────────────────
# Adicionamos status_emoji e status_text na tabela users via migration-like alter
# Para SQLite, vamos usar uma tabela separada para evitar ALTER TABLE
class UserStatus(db.Model):
    __tablename__ = "user_status"
    username    = db.Column(db.String(60), db.ForeignKey("users.username"), primary_key=True)
    status_text = db.Column(db.String(80), default="")
    status_emoji = db.Column(db.String(10), default="")
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow)
    def to_dict(self):
        return {"emoji":self.status_emoji,"text":self.status_text}

# ── API: Reações ──────────────────────────────────────────────────
@app.route("/api/posts/<pid>/react", methods=["POST"])
def react_post(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    p = Post.query.get(pid)
    if not p: return jsonify({"error":"Não encontrado"}), 404
    emoji = request.get_json().get("emoji","❤️")
    existing = PostReaction.query.filter_by(post_id=pid, username=me).first()
    if existing:
        if existing.emoji == emoji: db.session.delete(existing)
        else: existing.emoji = emoji
    else:
        db.session.add(PostReaction(post_id=pid, username=me, emoji=emoji))
    db.session.commit()
    # Contagem por emoji
    reactions = PostReaction.query.filter_by(post_id=pid).all()
    counts = {}
    for r in reactions: counts[r.emoji] = counts.get(r.emoji, 0) + 1
    my_reaction = PostReaction.query.filter_by(post_id=pid, username=me).first()
    return jsonify({"reactions": counts, "my_reaction": my_reaction.emoji if my_reaction else None})

@app.route("/api/posts/<pid>/reactions")
def get_reactions(pid):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    reactions = PostReaction.query.filter_by(post_id=pid).all()
    counts = {}
    for r in reactions: counts[r.emoji] = counts.get(r.emoji, 0) + 1
    my_reaction = PostReaction.query.filter_by(post_id=pid, username=me).first()
    return jsonify({"reactions": counts, "my_reaction": my_reaction.emoji if my_reaction else None})

# ── API: Conquistas ───────────────────────────────────────────────
@app.route("/api/achievements/<username>")
def get_achievements(username):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    achievements = Achievement.query.filter_by(username=username).order_by(Achievement.earned_at).all()
    return jsonify([a.to_dict() for a in achievements])

# ── API: Status ───────────────────────────────────────────────────
@app.route("/api/me/status", methods=["POST"])
def set_status():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json()
    s = UserStatus.query.get(me)
    if not s:
        s = UserStatus(username=me)
        db.session.add(s)
    s.status_emoji = d.get("emoji","")[:2]
    s.status_text  = d.get("text","")[:80]
    s.updated_at   = datetime.utcnow()
    db.session.commit()
    sse_broadcast("status_update", {"username":me,"emoji":s.status_emoji,"text":s.status_text})
    return jsonify(s.to_dict())

@app.route("/api/users/<username>/status")
def get_user_status(username):
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    s = UserStatus.query.get(username)
    return jsonify(s.to_dict() if s else {"emoji":"","text":""})

# ── API: Trending ─────────────────────────────────────────────────
@app.route("/api/trending")
def api_trending():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    cutoff = datetime.utcnow() - timedelta(hours=48)
    recent = Post.query.filter(Post.timestamp >= cutoff).all()
    words = []
    stopwords = {"de","a","o","que","e","do","da","em","um","para","com","uma","os","no","se","na","por","mais","as","dos","como","mas","ao","ele","das","à","seu","sua","ou","ser","quando","muito","nos","já","também","só","pelo","pela","até","isso","ela","entre","era","depois","sem","mesmo","aos","seus","quem","nas","me","esse","eles","estão","você","tinha","foram","essa","num","nem","suas","meu","às","minha","têm","numa","pelos","pelas","foi","nós","nossa","tendo"}
    for p in recent:
        for w in re.findall(r'\b[a-záéíóúâêôãõçàü]{4,}\b', (p.content or "").lower()):
            if w not in stopwords: words.append(w)
    counts = Counter(words).most_common(10)
    return jsonify([{"word": w, "count": c} for w,c in counts])

# ── API: FaeBot ───────────────────────────────────────────────────
@app.route("/api/faebot", methods=["POST"])
def faebot_chat():
    me = require_auth()
    if not me: return jsonify({"error":"Unauthorized"}), 401
    d = request.get_json()
    user_msg = d.get("message","").strip()
    history  = d.get("history", [])
    if not user_msg: return jsonify({"error":"Mensagem vazia"}), 400
    u = User.query.get(me)
    # Contexto do sistema
    system_prompt = f"""Você é o FaeBot, assistente de IA da FaeNet — a rede social da Escola Técnica Estadual Santa Cruz (ETESC/FAETEC). 
Você ajuda alunos e professores com dúvidas escolares, acadêmicas e sobre a plataforma.
O usuário atual se chama {u.name}, está no curso de {u.curso}, turma {u.turma}.
Seja sempre simpático, didático e use emojis para tornar as respostas mais amigáveis.
Quando for explicar conteúdo escolar, use exemplos práticos e linguagem acessível.
Se não souber algo, diga honestamente e sugira onde o aluno pode buscar ajuda.
Responda sempre em português brasileiro."""
    messages = []
    for h in history[-10:]:  # últimas 10 mensagens
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_msg})
    try:
        import urllib.request
        payload = json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "system": system_prompt,
            "messages": messages
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type":"application/json","anthropic-version":"2023-06-01"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            reply = result["content"][0]["text"]
    except Exception as e:
        # Fallback inteligente sem API key
        reply = _faebot_fallback(user_msg, u)
    return jsonify({"reply": reply})

def _faebot_fallback(msg, u):
    """Respostas de fallback quando API não está disponível."""
    msg_lower = msg.lower()
    if any(w in msg_lower for w in ["olá","oi","hello","bom dia","boa tarde","boa noite"]):
        return f"Olá, {u.name}! 👋 Sou o FaeBot, seu assistente da FaeNet! Como posso te ajudar hoje? Pode me perguntar sobre matérias, estágios, dúvidas acadêmicas ou sobre a plataforma! 🤖✨"
    if any(w in msg_lower for w in ["python","código","programar","variável","função","loop","lista"]):
        return "Ótima pergunta sobre programação! 💻 Para te ajudar melhor, preciso que você descreva sua dúvida com mais detalhes. Qual é o erro que está aparecendo ou o conceito que não está entendendo? 🐍"
    if any(w in msg_lower for w in ["estágio","estagio","emprego","vaga","trabalho"]):
        return f"Para vagas de estágio do curso de {u.curso}, acesse o **Hub do Curso** aqui na FaeNet! 📋 Lá os moderadores postam as vagas atualizadas. Você também pode verificar o CIEE e IEL! 🚀"
    if any(w in msg_lower for w in ["prova","nota","avaliação","matéria","aula"]):
        return "Para verificar datas de provas e conteúdos, acesse o **Hub do Curso** na FaeNet! 📅 Os professores postam os avisos por lá. Se tiver dúvidas sobre matéria, me explica o assunto que tento ajudar! 📚"
    if any(w in msg_lower for w in ["obrigado","valeu","thanks","vlw"]):
        return f"De nada, {u.name}! 😊 Estou sempre aqui para ajudar! Se surgir mais alguma dúvida, é só me chamar! 🤖💙"
    return f"Entendi sua pergunta! 🤔 Sou o FaeBot e estou aqui para ajudar alunos da ETESC. Pode me fazer perguntas sobre matérias, programação, estágios, datas de provas ou sobre como usar a FaeNet! Como posso te ajudar, {u.name}? 🌟"

# Patch create_post e follow para disparar check_badges + SSE
_orig_create_post = create_post.__wrapped__ if hasattr(create_post,'__wrapped__') else None

@app.after_request
def after_request_badges(response):
    """Hook para verificar conquistas após criação de posts e follows."""
    return response
