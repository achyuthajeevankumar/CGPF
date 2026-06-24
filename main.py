import os
import bcrypt

# Patch bcrypt for passlib compatibility in newer python environments
if not hasattr(bcrypt, "__about__"):
    class About:
        pass
    about = About()
    about.__version__ = getattr(bcrypt, "__version__", "4.0.0")
    bcrypt.__about__ = about

# Clean CLOUDINARY_URL from env if invalid (e.g. empty string or placeholder) to prevent Cloudinary SDK from crashing on import
cloudinary_url = os.environ.get("CLOUDINARY_URL")
if cloudinary_url and not cloudinary_url.startswith("cloudinary://"):
    os.environ.pop("CLOUDINARY_URL", None)

import shutil
import json
from datetime import datetime
from urllib.parse import quote, unquote
from typing import List, Optional

from fastapi import FastAPI, Depends, Request, Form, File, UploadFile, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import models
import auth
from database import engine, get_db, SessionLocal

import cloudinary
import cloudinary.uploader

# Configure Cloudinary (automatically loads CLOUDINARY_URL env var if present)
cloudinary.config(secure=True)

# Initialize Database tables
models.Base.metadata.create_all(bind=engine)

# Ensure local upload folders exist (as a local fallback or legacy)
os.makedirs("static/uploads/churches", exist_ok=True)
os.makedirs("static/uploads/media", exist_ok=True)
os.makedirs("static/uploads/profiles", exist_ok=True)

app = FastAPI(title="Calvary Gospel Prayer Fellowship")

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates Setup
templates = Jinja2Templates(directory="templates")

# Helper to set flash message cookie
def set_flash_message(response: RedirectResponse, message: str, category: str = "info"):
    messages = [(category, message)]
    response.set_cookie(
        "flash_messages", 
        quote(json.dumps(messages)), 
        max_age=10, 
        httponly=False  # Allow reading by JS if needed, but primarily consumed by templates
    )

# Template Render Helper injects global variables
def render_template(template_name: str, request: Request, context: dict = None):
    if context is None:
        context = {}
    
    # Check flash messages
    messages = []
    flash_cookie = request.cookies.get("flash_messages")
    if flash_cookie:
        try:
            messages = json.loads(unquote(flash_cookie))
        except Exception:
            pass

    context["request"] = request
    context["current_user"] = getattr(request.state, "user", None)
    context["global_settings"] = getattr(request.state, "settings", None)
    context["messages"] = messages
    
    response = templates.TemplateResponse(template_name, context)
    
    # Clear the flash messages cookie once consumed
    if flash_cookie:
        response.delete_cookie("flash_messages")
        
    return response

# Custom Middleware to intercept requests and load session/settings
@app.middleware("http")
async def add_session_and_settings(request: Request, call_next):
    # Retrieve DB session
    db = SessionLocal()
    try:
        user = None
        token = request.cookies.get("session_token")
        if token:
            session_data = auth.verify_session_token(token)
            if session_data:
                user = db.query(models.User).filter(models.User.id == session_data["user_id"]).first()
        
        request.state.user = user
        
        # Load settings
        settings = db.query(models.Settings).first()
        request.state.settings = settings
    finally:
        db.close()
        
    response = await call_next(request)
    return response


# ==============================================================================
# PUBLIC ROUTER
# ==============================================================================

@app.get("/debug-db-run")
def debug_db_run():
    from sqlalchemy import text
    db = SessionLocal()
    try:
        # Run raw SQL to check tables
        result = db.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';"))
        tables = [row[0] for row in result]
        
        # Check if tables exist
        counts = {}
        for table in tables:
            try:
                res = db.execute(text(f"SELECT COUNT(*) FROM {table};"))
                counts[table] = res.scalar()
            except Exception as e:
                counts[table] = f"Error: {str(e)}"
                db.rollback()
                
        # Try to run seed logic and print exactly what it does
        seed_logs = []
        import models
        from auth import hash_password
        
        # Let's seed manually here to see exactly where it fails or succeeds!
        admin_user = db.query(models.User).filter(models.User.username == "admin").first()
        if not admin_user:
            admin_user = models.User(
                username="admin",
                email="admin@calvarygospel.org",
                password_hash=hash_password("adminpassword123"),
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            seed_logs.append("Admin created")
        else:
            seed_logs.append("Admin already exists")
            
        church_count = db.query(models.Church).count()
        if church_count == 0:
            initial_churches = [
                {"name": "Dubacherla", "address": "Dubacharala Gandhi colony", "map_link": "https://maps.app.goo.gl/q2v12ih589cvSZrC6", "contact": "+91 97010 20668", "timings": "Sunday morning 6:00 to 8:30, Saturday night 7:00 to 10:00", "about": "Welcome to Calvary Gospel Prayer Fellowship in Dubacherla."},
                {"name": "Ramachandrapuram", "address": "Ramachandrapuram", "map_link": "https://maps.app.goo.gl/n3LddBQUWJqH7TtC9", "contact": "+91 97010 20668", "timings": "Sunday morning 11:00 to 1:00", "about": "Welcome to our Ramachandrapuram branch."},
                {"name": "Marelamudi", "address": "Marelamudi", "map_link": "https://maps.app.goo.gl/rKteXgSXBUyUsRJH6", "contact": "+91 97010 20668", "timings": "Sunday morning 12:30 to 2:00", "about": "Welcome to Marelamudi Calvary Gospel branch."},
                {"name": "Dubacherla Colony", "address": "Dubacherla Colony", "map_link": "https://maps.app.goo.gl/q2v12ih589cvSZrC6", "contact": "+91 97010 20668", "timings": "Sunday morning 8:00 to 10:00", "about": "Our Dubacherla Colony branch is growing."}
            ]
            for c in initial_churches:
                church = models.Church(
                    name=c["name"],
                    address=c["address"],
                    map_link=c["map_link"],
                    contact=c["contact"],
                    timings=c["timings"],
                    about=c["about"]
                )
                db.add(church)
                db.commit()
                seed_logs.append(f"Seeded church {c['name']}")
        else:
            seed_logs.append(f"Churches already exist: {church_count}")
            
        # Re-query
        re_tables = db.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';"))
        re_counts = {}
        for table in [row[0] for row in re_tables]:
            res = db.execute(text(f"SELECT COUNT(*) FROM {table};"))
            re_counts[table] = res.scalar()
            
        return {
            "tables": tables,
            "initial_counts": counts,
            "seed_logs": seed_logs,
            "final_counts": re_counts
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()

@app.get("/debug-db")
def debug_db(db: Session = Depends(get_db)):
    db_type = "PostgreSQL" if "postgresql" in str(db.bind.url) else "SQLite"
    churches_count = db.query(models.Church).count()
    users_count = db.query(models.User).count()
    settings_count = db.query(models.Settings).count()
    
    seeded = False
    if churches_count == 0:
        try:
            import seed
            seed.seed_database()
            seeded = True
            churches_count = db.query(models.Church).count()
            users_count = db.query(models.User).count()
        except Exception as e:
            return {"error": f"Seeding failed: {str(e)}", "db_type": db_type}
            
    return {
        "db_type": db_type,
        "database_url_configured": bool(os.environ.get("DATABASE_URL")),
        "churches_count": churches_count,
        "users_count": users_count,
        "settings_count": settings_count,
        "auto_seeded": seeded
    }

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    churches = db.query(models.Church).all()
    founder = db.query(models.FounderProfile).first()
    pastor = db.query(models.PastorProfile).first()
    
    return render_template(
        "index.html", 
        request, 
        {
            "active_page": "home",
            "churches": churches,
            "founder": founder,
            "pastor": pastor
        }
    )

@app.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "", db: Session = Depends(get_db)):
    # Search churches by name (case-insensitive)
    churches = db.query(models.Church).filter(models.Church.name.like(f"%{q}%")).all()
    return render_template(
        "search.html",
        request,
        {
            "query": q,
            "churches": churches
        }
    )

@app.get("/church/{id}", response_class=HTMLResponse)
def church_detail(id: int, request: Request, db: Session = Depends(get_db)):
    church = db.query(models.Church).filter(models.Church.id == id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church branch not found")
        
    # Get approved media highlights (e.g. recent 6 items)
    media_highlights = db.query(models.Media).filter(
        models.Media.church_id == id,
        models.Media.status == "approved"
    ).order_by(models.Media.created_at.desc()).limit(6).all()
    
    return render_template(
        "church_detail.html",
        request,
        {
            "church": church,
            "media_highlights": media_highlights
        }
    )

@app.get("/church/{id}/gallery", response_class=HTMLResponse)
def church_gallery(id: int, request: Request, db: Session = Depends(get_db)):
    church = db.query(models.Church).filter(models.Church.id == id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church branch not found")
        
    media_items = db.query(models.Media).filter(
        models.Media.church_id == id,
        models.Media.status == "approved"
    ).order_by(models.Media.created_at.desc()).all()
    
    return render_template(
        "church_gallery.html",
        request,
        {
            "church": church,
            "media_items": media_items
        }
    )

@app.get("/founder", response_class=HTMLResponse)
def founder_view(request: Request, db: Session = Depends(get_db)):
    founder = db.query(models.FounderProfile).first()
    return render_template(
        "founder.html",
        request,
        {
            "active_page": "founder",
            "founder": founder
        }
    )

@app.get("/pastor", response_class=HTMLResponse)
def pastor_view(request: Request, db: Session = Depends(get_db)):
    pastor = db.query(models.PastorProfile).first()
    return render_template(
        "pastor.html",
        request,
        {
            "active_page": "pastor",
            "pastor": pastor
        }
    )


# ==============================================================================
# AUTHENTICATION ROUTER
# ==============================================================================

@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=303)
    return render_template("register.html", request)

@app.post("/register")
def register_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/register", status_code=303)
    
    if password != confirm_password:
        set_flash_message(response, "Passwords do not match.", "error")
        return response
        
    # Check if username or email already exists
    existing_user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == email)
    ).first()
    if existing_user:
        set_flash_message(response, "Username or Email already registered.", "error")
        return response
        
    hashed = auth.hash_password(password)
    user = models.User(
        username=username,
        email=email,
        password_hash=hashed,
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Audit log
    audit = models.AuditLog(user_id=user.id, action="registered_account", target_type="user", target_id=user.id)
    db.add(audit)
    db.commit()
    
    response = RedirectResponse(url="/login", status_code=303)
    set_flash_message(response, "Registration successful! You can now log in.", "success")
    return response

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if getattr(request.state, "user", None):
        return RedirectResponse(url="/dashboard", status_code=303)
    return render_template("login.html", request, {"active_page": "login"})

@app.post("/login")
def login_user(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Can login by username or email
    user = db.query(models.User).filter(
        (models.User.username == username) | (models.User.email == username)
    ).first()
    
    if not user or not auth.verify_password(password, user.password_hash):
        response = RedirectResponse(url="/login", status_code=303)
        set_flash_message(response, "Invalid credentials.", "error")
        return response
        
    # Create session token
    token = auth.create_session_token(user.id, user.role)
    
    # Redirection based on role
    dest = "/admin/dashboard" if user.role == "admin" else "/dashboard"
    response = RedirectResponse(url=dest, status_code=303)
    response.set_cookie("session_token", token, httponly=True, max_age=7 * 86400)
    set_flash_message(response, f"Welcome back, {user.username}!", "success")
    return response

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_form(request: Request):
    if getattr(request.state, "user", None) and request.state.user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return render_template("admin_login.html", request)

@app.post("/admin/login")
def admin_login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or user.role != "admin" or not auth.verify_password(password, user.password_hash):
        response = RedirectResponse(url="/admin/login", status_code=303)
        set_flash_message(response, "Invalid admin credentials.", "error")
        return response
        
    token = auth.create_session_token(user.id, user.role)
    response = RedirectResponse(url="/admin/dashboard", status_code=303)
    response.set_cookie("session_token", token, httponly=True, max_age=7 * 86400)
    set_flash_message(response, "Authenticated successfully as administrator.", "success")
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_token")
    set_flash_message(response, "Logged out successfully.", "success")
    return response


# ==============================================================================
# USER DASHBOARD & UPLOADS ROUTER
# ==============================================================================

@app.get("/dashboard", response_class=HTMLResponse)
def user_dashboard(
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Stats
    total = db.query(models.Media).filter(models.Media.uploader_id == current_user.id).count()
    approved = db.query(models.Media).filter(models.Media.uploader_id == current_user.id, models.Media.status == "approved").count()
    pending = db.query(models.Media).filter(models.Media.uploader_id == current_user.id, models.Media.status == "pending").count()
    
    churches = db.query(models.Church).all()
    media_items = db.query(models.Media).filter(models.Media.uploader_id == current_user.id).order_by(models.Media.created_at.desc()).all()
    
    return render_template(
        "dashboard.html",
        request,
        {
            "active_page": "dashboard",
            "churches": churches,
            "media_items": media_items,
            "total_uploads": total,
            "approved_uploads": approved,
            "pending_uploads": pending
        }
    )

@app.post("/upload")
async def handle_media_upload(
    church_id: int = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Setup response redirect
    response = RedirectResponse(url="/dashboard#my-media", status_code=303)
    
    uploaded_count = 0
    for file in files:
        if not file.filename:
            continue
            
        # Read size and content validation
        contents = await file.read()
        file_size = len(contents)
        
        # Check bounds
        content_type = file.content_type
        is_image = content_type.startswith("image/")
        is_video = content_type.startswith("video/")
        
        if not (is_image or is_video):
            set_flash_message(response, f"Only image or video uploads are allowed (skipped {file.filename}).", "error")
            return response
            
        if is_image and file_size > 5 * 1024 * 1024:
            set_flash_message(response, f"Image {file.filename} size must be less than 5MB.", "error")
            return response
            
        if is_video and file_size > 50 * 1024 * 1024:
            set_flash_message(response, f"Video {file.filename} size must be less than 50MB.", "error")
            return response
            
        # Reset read pointer
        await file.seek(0)
        
        # Save file (Cloudinary if CLOUDINARY_URL exists, otherwise local fallback)
        use_cloudinary = bool(os.environ.get("CLOUDINARY_URL"))
        if use_cloudinary:
            try:
                if is_video:
                    upload_result = cloudinary.uploader.upload_large(
                        file.file,
                        resource_type="video",
                        folder="cgpf/media"
                    )
                else:
                    upload_result = cloudinary.uploader.upload(
                        file.file,
                        resource_type="image",
                        folder="cgpf/media"
                    )
                relative_path = upload_result.get("secure_url")
            except Exception as e:
                set_flash_message(response, f"Cloudinary upload failed for {file.filename}: {str(e)}", "error")
                return response
        else:
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"{timestamp}_{uploaded_count}_{file.filename.replace(' ', '_')}"
            relative_path = f"/static/uploads/media/{filename}"
            full_path = os.path.join("static", "uploads", "media", filename)
            try:
                with open(full_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)
            except Exception as e:
                set_flash_message(response, f"Failed to write file {file.filename} to local storage.", "error")
                return response
            
        # Write to DB
        media = models.Media(
            church_id=church_id,
            uploader_id=current_user.id,
            title=title,
            description=description,
            file_path=relative_path,
            file_type="image" if is_image else "video",
            status="pending"  # Needs admin approval
        )
        db.add(media)
        db.commit()
        db.refresh(media)
        
        # Log audit
        audit = models.AuditLog(user_id=current_user.id, action="uploaded_media", target_type="media", target_id=media.id)
        db.add(audit)
        db.commit()
        
        uploaded_count += 1
        
    if uploaded_count > 0:
        set_flash_message(response, f"Successfully uploaded {uploaded_count} media item(s)! Awaiting administrator approval.", "success")
    else:
        set_flash_message(response, "No files were uploaded.", "warning")
        
    return response

@app.post("/media/delete/{id}")
def delete_own_media(
    id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    media = db.query(models.Media).filter(models.Media.id == id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
        
    # Check authorization
    if media.uploader_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this media")
        
    # Remove file from disk
    file_rel_path = media.file_path.lstrip("/")
    if os.path.exists(file_rel_path):
        os.remove(file_rel_path)
        
    db.delete(media)
    
    # Audit log
    audit = models.AuditLog(user_id=current_user.id, action="deleted_media", target_type="media", target_id=id)
    db.add(audit)
    db.commit()
    
    dest = "/admin/dashboard#media" if current_user.role == "admin" else "/dashboard#my-media"
    response = RedirectResponse(url=dest, status_code=303)
    set_flash_message(response, "Media deleted permanently.", "success")
    return response


# ==============================================================================
# ADMINISTRATOR ROUTER
# ==============================================================================

@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    # Counters
    total_users = db.query(models.User).count()
    total_churches = db.query(models.Church).count()
    total_photos = db.query(models.Media).filter(models.Media.file_type == "image", models.Media.status == "approved").count()
    total_videos = db.query(models.Media).filter(models.Media.file_type == "video", models.Media.status == "approved").count()
    
    # Data Lists
    churches = db.query(models.Church).all()
    media_items = db.query(models.Media).order_by(models.Media.created_at.desc()).all()
    founder = db.query(models.FounderProfile).first()
    pastor = db.query(models.PastorProfile).first()
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    audit_logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(50).all()
    
    return render_template(
        "admin_dashboard.html",
        request,
        {
            "active_page": "admin_dashboard",
            "total_users": total_users,
            "total_churches": total_churches,
            "total_photos": total_photos,
            "total_videos": total_videos,
            "churches": churches,
            "media_items": media_items,
            "founder": founder,
            "pastor": pastor,
            "users": users,
            "audit_logs": audit_logs
        }
    )

@app.post("/admin/churches/add")
def admin_add_church(
    name: str = Form(...),
    address: Optional[str] = Form(None),
    map_link: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    timings: Optional[str] = Form(None),
    about: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#churches", status_code=303)
    
    # Check duplicate
    exists = db.query(models.Church).filter(models.Church.name == name).first()
    if exists:
        set_flash_message(response, f"Branch '{name}' already exists.", "error")
        return response
        
    cover_path = None
    if cover_image and cover_image.filename:
        use_cloudinary = bool(os.environ.get("CLOUDINARY_URL"))
        if use_cloudinary:
            try:
                upload_result = cloudinary.uploader.upload(
                    cover_image.file,
                    resource_type="image",
                    folder="cgpf/churches"
                )
                cover_path = upload_result.get("secure_url")
            except Exception as e:
                set_flash_message(response, f"Cloudinary upload failed for cover image: {str(e)}", "error")
                return response
        else:
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"{timestamp}_{cover_image.filename.replace(' ', '_')}"
            cover_path = f"/static/uploads/churches/{filename}"
            full_path = os.path.join("static", "uploads", "churches", filename)
            try:
                with open(full_path, "wb") as f:
                    shutil.copyfileobj(cover_image.file, f)
            except Exception as e:
                set_flash_message(response, "Failed to write cover image to local storage.", "error")
                return response
            
    church = models.Church(
        name=name,
        address=address,
        map_link=map_link,
        contact=contact,
        timings=timings,
        about=about,
        cover_image=cover_path
    )
    db.add(church)
    db.commit()
    db.refresh(church)
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="created_church", target_type="church", target_id=church.id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, f"Church '{name}' added successfully.", "success")
    return response

@app.post("/admin/churches/edit/{id}")
def admin_edit_church(
    id: int,
    name: str = Form(...),
    address: Optional[str] = Form(None),
    map_link: Optional[str] = Form(None),
    contact: Optional[str] = Form(None),
    timings: Optional[str] = Form(None),
    about: Optional[str] = Form(None),
    cover_image: Optional[UploadFile] = File(None),
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#churches", status_code=303)
    church = db.query(models.Church).filter(models.Church.id == id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")
        
    church.name = name
    church.address = address
    church.map_link = map_link
    church.contact = contact
    church.timings = timings
    church.about = about
    
    if cover_image and cover_image.filename:
        # Delete old file if it was stored locally
        if church.cover_image:
            old_rel = church.cover_image.lstrip("/")
            if not old_rel.startswith("http") and os.path.exists(old_rel):
                try:
                    os.remove(old_rel)
                except Exception:
                    pass
                
        use_cloudinary = bool(os.environ.get("CLOUDINARY_URL"))
        if use_cloudinary:
            try:
                upload_result = cloudinary.uploader.upload(
                    cover_image.file,
                    resource_type="image",
                    folder="cgpf/churches"
                )
                church.cover_image = upload_result.get("secure_url")
            except Exception as e:
                set_flash_message(response, f"Cloudinary upload failed for cover image: {str(e)}", "error")
                return response
        else:
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"{timestamp}_{cover_image.filename.replace(' ', '_')}"
            cover_path = f"/static/uploads/churches/{filename}"
            full_path = os.path.join("static", "uploads", "churches", filename)
            try:
                with open(full_path, "wb") as f:
                    shutil.copyfileobj(cover_image.file, f)
                church.cover_image = cover_path
            except Exception as e:
                set_flash_message(response, "Failed to write cover image to local storage.", "error")
                return response
        
    db.commit()
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="edited_church", target_type="church", target_id=id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, f"Church '{name}' updated successfully.", "success")
    return response

@app.post("/admin/churches/delete/{id}")
def admin_delete_church(
    id: int,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#churches", status_code=303)
    church = db.query(models.Church).filter(models.Church.id == id).first()
    if not church:
        raise HTTPException(status_code=404, detail="Church not found")
        
    # Delete cover
    if church.cover_image:
        old_rel = church.cover_image.lstrip("/")
        if os.path.exists(old_rel):
            os.remove(old_rel)
            
    # Delete associated media files on disk
    associated_media = db.query(models.Media).filter(models.Media.church_id == id).all()
    for item in associated_media:
        file_rel_path = item.file_path.lstrip("/")
        if os.path.exists(file_rel_path):
            os.remove(file_rel_path)
            
    db.delete(church)
    db.commit()
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="deleted_church", target_type="church", target_id=id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, "Church branch and related media deleted.", "success")
    return response

@app.post("/admin/media/approve/{id}")
def admin_approve_media(
    id: int,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#media", status_code=303)
    media = db.query(models.Media).filter(models.Media.id == id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
        
    media.status = "approved"
    db.commit()
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="approved_media", target_type="media", target_id=id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, "Media approved successfully.", "success")
    return response

@app.post("/admin/media/reject/{id}")
def admin_reject_media(
    id: int,
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#media", status_code=303)
    media = db.query(models.Media).filter(models.Media.id == id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
        
    media.status = "rejected"
    db.commit()
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="rejected_media", target_type="media", target_id=id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, "Media marked as rejected.", "success")
    return response

@app.post("/admin/founder")
def admin_update_founder(
    name: str = Form(...),
    birth_date: Optional[str] = Form(None),
    death_date: Optional[str] = Form(None),
    about: Optional[str] = Form(None),
    highlights: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#founder", status_code=303)
    founder = db.query(models.FounderProfile).first()
    
    if not founder:
        founder = models.FounderProfile(name=name)
        db.add(founder)
        db.commit()
        db.refresh(founder)
        
    founder.name = name
    founder.birth_date = birth_date
    founder.death_date = death_date
    founder.about = about
    founder.highlights = highlights
    
    if photo and photo.filename:
        # Delete old photo if it was stored locally
        if founder.photo:
            old_rel = founder.photo.lstrip("/")
            if not old_rel.startswith("http") and os.path.exists(old_rel):
                try:
                    os.remove(old_rel)
                except Exception:
                    pass
                
        use_cloudinary = bool(os.environ.get("CLOUDINARY_URL"))
        if use_cloudinary:
            try:
                upload_result = cloudinary.uploader.upload(
                    photo.file,
                    resource_type="image",
                    folder="cgpf/profiles"
                )
                founder.photo = upload_result.get("secure_url")
            except Exception as e:
                set_flash_message(response, f"Cloudinary upload failed for founder photo: {str(e)}", "error")
                return response
        else:
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"{timestamp}_founder_{photo.filename.replace(' ', '_')}"
            photo_path = f"/static/uploads/profiles/{filename}"
            full_path = os.path.join("static", "uploads", "profiles", filename)
            try:
                with open(full_path, "wb") as f:
                    shutil.copyfileobj(photo.file, f)
                founder.photo = photo_path
            except Exception as e:
                set_flash_message(response, "Failed to write photo to local storage.", "error")
                return response
        
    db.commit()
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="updated_founder_profile", target_type="founder", target_id=founder.id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, "Founder profile updated successfully.", "success")
    return response

@app.post("/admin/pastor")
def admin_update_pastor(
    name: str = Form(...),
    role: str = Form("Pastor"),
    about: Optional[str] = Form(None),
    message: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#pastor", status_code=303)
    pastor = db.query(models.PastorProfile).first()
    
    if not pastor:
        pastor = models.PastorProfile(name=name, role=role)
        db.add(pastor)
        db.commit()
        db.refresh(pastor)
        
    pastor.name = name
    pastor.role = role
    pastor.about = about
    pastor.message = message
    
    if photo and photo.filename:
        # Delete old photo if it was stored locally
        if pastor.photo:
            old_rel = pastor.photo.lstrip("/")
            if not old_rel.startswith("http") and os.path.exists(old_rel):
                try:
                    os.remove(old_rel)
                except Exception:
                    pass
                
        use_cloudinary = bool(os.environ.get("CLOUDINARY_URL"))
        if use_cloudinary:
            try:
                upload_result = cloudinary.uploader.upload(
                    photo.file,
                    resource_type="image",
                    folder="cgpf/profiles"
                )
                pastor.photo = upload_result.get("secure_url")
            except Exception as e:
                set_flash_message(response, f"Cloudinary upload failed for pastor photo: {str(e)}", "error")
                return response
        else:
            timestamp = int(datetime.utcnow().timestamp())
            filename = f"{timestamp}_pastor_{photo.filename.replace(' ', '_')}"
            photo_path = f"/static/uploads/profiles/{filename}"
            full_path = os.path.join("static", "uploads", "profiles", filename)
            try:
                with open(full_path, "wb") as f:
                    shutil.copyfileobj(photo.file, f)
                pastor.photo = photo_path
            except Exception as e:
                set_flash_message(response, "Failed to write photo to local storage.", "error")
                return response
        
    db.commit()
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="updated_pastor_profile", target_type="pastor", target_id=pastor.id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, "Pastor profile updated successfully.", "success")
    return response

@app.post("/settings")
def admin_update_settings(
    youtube_link: Optional[str] = Form(None),
    hero_title: Optional[str] = Form(None),
    hero_subtitle: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    contact_email: Optional[str] = Form(None),
    current_admin: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    response = RedirectResponse(url="/admin/dashboard#settings", status_code=303)
    settings = db.query(models.Settings).first()
    
    if not settings:
        settings = models.Settings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
        
    settings.youtube_link = youtube_link
    settings.hero_title = hero_title
    settings.hero_subtitle = hero_subtitle
    settings.contact_phone = contact_phone
    settings.contact_email = contact_email
    db.commit()
    
    # Audit log
    audit = models.AuditLog(user_id=current_admin.id, action="updated_global_settings", target_type="settings", target_id=settings.id)
    db.add(audit)
    db.commit()
    
    set_flash_message(response, "Global web settings updated successfully.", "success")
    return response
