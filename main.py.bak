"""
Budget Tracker - Hybrid FastAPI + aiogram + SQLite
Minimal RAM footprint (<150MB target)
"""
import os
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, 
    create_engine, select, func, desc
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, date
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./budget.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "123456:TEST_TOKEN")  # Will need real token for production
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://153.76.249.189:8088").rstrip("/")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # optional Telegram Web App HTTPS endpoint

# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    type = Column(String, nullable=False)  # 'income' or 'expense'
    icon = Column(String, default="💰")
    color = Column(String, default="#3B82F6")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(Float, nullable=False)
    description = Column(String)
    category_id = Column(Integer, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    type = Column(String, nullable=False)  # 'income' or 'expense'
    is_recurring = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)  # Soft archive for monthly reset
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic schemas
class CategoryBase(BaseModel):
    name: str
    type: str  # 'income' or 'expense'
    icon: Optional[str] = "💰"
    color: Optional[str] = "#3B82F6"

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    amount: float = Field(gt=0)
    description: Optional[str] = None
    category_id: int
    date: Optional[datetime] = None
    type: str  # 'income' or 'expense'
    is_recurring: bool = False

class TransactionCreate(TransactionBase):
    pass

class TransactionResponse(TransactionBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class StatsResponse(BaseModel):
    total_income: float
    total_expense: float
    balance: float
    transaction_count: int
    period_start: date
    period_end: date

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)
    
    # Create default categories if they don't exist
    db = SessionLocal()
    try:
        # Check if categories exist
        if db.query(Category).count() == 0:
            default_categories = [
                # Income categories
                {"name": "Salary", "type": "income", "icon": "💵", "color": "#10B981"},
                {"name": "Freelance", "type": "income", "icon": "💻", "color": "#059669"},
                {"name": "Investment", "type": "income", "icon": "📈", "color": "#047857"},
                {"name": "Other Income", "type": "income", "icon": "💰", "color": "#6B7280"},
                # Expense categories
                {"name": "Food & Groceries", "type": "expense", "icon": "🛒", "color": "#EF4444"},
                {"name": "Transport", "type": "expense", "icon": "🚗", "color": "#F97316"},
                {"name": "Housing", "type": "expense", "icon": "🏠", "color": "#DC2626"},
                {"name": "Utilities", "type": "expense", "icon": "💡", "color": "#D946EF"},
                {"name": "Entertainment", "type": "expense", "icon": "🎬", "color": "#8B5CF6"},
                {"name": "Shopping", "type": "expense", "icon": "🛍️", "color": "#EC4899"},
                {"name": "Health", "type": "expense", "icon": "🏥", "color": "#EF4444"},
                {"name": "Education", "type": "expense", "icon": "📚", "color": "#6366F1"},
                {"name": "Other Expenses", "type": "expense", "icon": "💸", "color": "#6B7280"},
            ]
            
            for cat_data in default_categories:
                category = Category(**cat_data)
                db.add(category)
            
            db.commit()
    finally:
        db.close()

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    yield
    # Shutdown
    # Dispose engine to free connections
    engine.dispose()

app = FastAPI(
    title="Budget Tracker API",
    description="Hybrid FastAPI + aiogram budget tracker",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
@app.get("/")
async def root():
    # Serve web dashboard directly on root
    return FileResponse("/root/budget-tracker/static/dashboard.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Category endpoints
@app.get("/categories/", response_model=List[CategoryResponse])
async def get_categories(type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Category).filter(Category.is_active == True)
    if type:
        query = query.filter(Category.type == type)
    return query.all()

@app.post("/categories/", response_model=CategoryResponse)
async def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = Category(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

# Transaction endpoints
@app.get("/transactions/", response_model=List[TransactionResponse])
async def get_transactions(
    skip: int = 0, 
    limit: int = 100,
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Transaction).filter(Transaction.archived == False)
    if type:
        query = query.filter(Transaction.type == type)
    return query.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()

@app.post("/transactions/", response_model=TransactionResponse)
async def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    # Verify category exists and matches type
    category = db.query(Category).filter(Category.id == transaction.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.type != transaction.type:
        raise HTTPException(status_code=400, detail="Category type mismatch")
    
    db_transaction = Transaction(**transaction.model_dump())
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.post("/reset-month/")
async def reset_month(db: Session = Depends(get_db)):
    """Reset current active period by archiving all unarchived transactions."""
    now = datetime.utcnow()
    # Count how many we are archiving
    count = db.query(Transaction).filter(Transaction.archived == False).update({Transaction.archived: True})
    db.commit()
    return {"status": "success", "archived_transactions": count, "reset_at": now.isoformat()}

@app.get("/history-months/")
async def get_history_months(db: Session = Depends(get_db)):
    """Get list of past months that have recorded transactions."""
    # SQLite strftime for year-month
    res = db.query(
        func.strftime('%Y-%m', Transaction.date).label("month"),
        Transaction.type,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count")
    ).group_by("month", Transaction.type).order_by(desc("month")).all()
    
    months_dict = {}
    for month, tx_type, total, cnt in res:
        if month not in months_dict:
            months_dict[month] = {"month": month, "income": 0.0, "expense": 0.0, "transactions": 0}
        if tx_type == "income":
            months_dict[month]["income"] = total
        else:
            months_dict[month]["expense"] = total
        months_dict[month]["transactions"] += cnt
        
    for m in months_dict.values():
        m["balance"] = m["income"] - m["expense"]
        
    return list(months_dict.values())

@app.get("/report/")
async def get_report(db: Session = Depends(get_db)):
    """Category breakdown for the current month (non-archived)."""
    now = datetime.utcnow()
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    res = db.query(
        Category.id, Category.name, Category.icon, Category.type,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("count")
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.date >= start_month,
        Transaction.archived == False
    ).group_by(Category.id, Category.name, Category.icon, Category.type).all()

    out = []
    for cid, name, icon, ctype, total, count in res:
        out.append({
            "category_id": cid, "name": name, "icon": icon,
            "type": ctype, "total": float(total or 0), "count": count
        })
    out.sort(key=lambda r: r["total"], reverse=True)

    total_expense = sum(r["total"] for r in out if r["type"] == "expense")
    for r in out:
        r["pct"] = round(r["total"] / total_expense * 100, 1) if (r["type"] == "expense" and total_expense > 0) else 0.0
    return {"month": start_month.strftime("%Y-%m"), "total_expense": total_expense, "categories": out}

@app.get("/stats/", response_model=StatsResponse)
async def get_stats(
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if not period_start:
        period_start = date.today().replace(day=1)  # First day of current month
    if not period_end:
        period_end = date.today()  # Today
    
    # Convert to datetime for querying
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(period_end, datetime.max.time())
    
    # Query totals
    income_query = select(func.sum(Transaction.amount)).where(
        Transaction.type == "income",
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.archived == False
    )
    expense_query = select(func.sum(Transaction.amount)).where(
        Transaction.type == "expense",
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.archived == False
    )
    count_query = select(func.count(Transaction.id)).where(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt,
        Transaction.archived == False
    )
    
    total_income = db.execute(income_query).scalar() or 0.0
    total_expense = db.execute(expense_query).scalar() or 0.0
    transaction_count = db.execute(count_query).scalar() or 0
    
    return StatsResponse(
        total_income=total_income,
        total_expense=total_expense,
        balance=total_income - total_expense,
        transaction_count=transaction_count,
        period_start=period_start,
        period_end=period_end
    )

# Telegram Bot setup
def get_bot():
    token = os.getenv("BOT_TOKEN")
    if token and token != "123456:TEST_TOKEN":
        return Bot(token=token)
    return None

bot = get_bot()
dp = Dispatcher()

# Bot keyboards
def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="/start"))
    builder.add(KeyboardButton(text="/help"))
    builder.add(KeyboardButton(text="/stats"))
    builder.add(KeyboardButton(text="/report"))
    builder.add(KeyboardButton(text="/recent"))
    builder.add(KeyboardButton(text="/categories"))
    builder.add(KeyboardButton(text="/reset"))
    builder.add(KeyboardButton(text="🌐 Web Dashboard"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_web_button():
    buttons = [
        InlineKeyboardButton(text="🌐 Buka Dashboard Web", url=PUBLIC_URL)
    ]
    if WEBAPP_URL:
        buttons.append(InlineKeyboardButton(text="📱 Buka di Telegram (Web App)", web_app=WebAppInfo(url=WEBAPP_URL)))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])

def get_main_with_web():
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🌐 Buka Dashboard Web", url=PUBLIC_URL)]]
    )

# Bot handlers
@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "💰 **Sky Budget Tracker**\n\n"
        "Halo Bos! Sekarang Bos bisa interaksi penuh langsung di **Web Dashboard** tanpa perlu ribet ketik perintah di bot lagi. 😎\n\n"
        "Klik tombol **🌐 Buka Dashboard Web** di bawah buat langsung akses:\n"
        f"🔗 `{PUBLIC_URL}`\n\n"
        "Kalau tetap butuh info ringkas di sini:\n"
        "• `/stats` - Ringkasan saldo berjalan\n"
        "• `/report` - Pos pengeluaran terbanyak\n"
        "• `/recent` - 10 transaksi terakhir\n"
        "• `/reset` - Arsipkan bulan ini"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_web_button())

@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📋 **Sky Budget Help**\n\n"
        "**Langkah utama:**\n"
        "1️⃣ Tekan tombol **🌐 Buka Dashboard Web** di atas atau ketik `/web`\n"
        "2️⃣ Input transaksi via form web, atau via bot dengan format:\n"
        "   `50000 Kopi kopdar` atau `500k Gaji fulltime`\n"
        "3️⃣ Lihat **Breakdown Pengeluaran per Pos** di web (bar chart)\n"
        "4️⃣ Pada akhir bulan, tekan **Reset Bulan Ini (Arsipkan)** di web\n\n"
        "**Commands tetap aktif (untuk yang suka ketik):**\n"
        "• `/stats` - Statistik saldo berjalan (income/expense/balance)\n"
        "• `/report` - Breakdown pengeluaran per kategori\n"
        "• `/recent` - 10 transaksi terakhir\n"
        "• `/categories` - Daftar kategori aktif\n"
        "• `/reset` - Arsipkan transaksi bulan ini\n\n"
        f"**Web Dashboard:** `{PUBLIC_URL}`"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_web_button())

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if bot is None:
        await message.answer("Bot not configured. Please set BOT_TOKEN environment variable.")
        return
    
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        income = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == "income",
            Transaction.date >= start_month,
            Transaction.archived == False
        ).scalar() or 0.0
        
        expense = db.query(func.sum(Transaction.amount)).filter(
            Transaction.type == "expense",
            Transaction.date >= start_month,
            Transaction.archived == False
        ).scalar() or 0.0
        
        count = db.query(func.count(Transaction.id)).filter(
            Transaction.date >= start_month,
            Transaction.archived == False
        ).scalar() or 0
        
        balance = income - expense
        bal_icon = "🟢" if balance >= 0 else "🔴"
        
        text = (
            f"📊 **Statistik Bulan Ini ({now.strftime('%B %Y')})**\n\n"
            f"💰 Pemasukan: Rp {income:,.0f}\n"
            f"💸 Pengeluaran: Rp {expense:,.0f}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{bal_icon} Saldo: Rp {balance:,.0f}\n\n"
            f"📝 Total Transaksi: {count}x\n\n"
            "📈 Grafik breakdown pos & kontrol reset bulanan ada di web 👇"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=get_web_button())
    finally:
        db.close()

@dp.message(Command("recent"))
async def cmd_recent(message: Message):
    if bot is None:
        await message.answer("Bot not configured. Please set BOT_TOKEN environment variable.")
        return
        
    db = SessionLocal()
    try:
        txs = db.query(Transaction, Category.name, Category.icon).outerjoin(
            Category, Transaction.category_id == Category.id
        ).order_by(desc(Transaction.date)).limit(10).all()
        
        if not txs:
            await message.answer("Belum ada riwayat transaksi nih, Bos!", reply_markup=get_main_keyboard())
            return
            
        text = "🕒 **10 Transaksi Terakhir:**\n\n"
        for t, cat_name, cat_icon in txs:
            icon = "🟢" if t.type == "income" else "🔴"
            desc_text = f" ({t.description})" if t.description else ""
            cat_display = f"{cat_icon or '🏷️'} {cat_name or 'Umum'}"
            date_str = t.date.strftime("%d/%m %H:%M")
            text += f"{icon} `Rp {t.amount:,.0f}` • {cat_display}{desc_text} - _{date_str}_\n"
            
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
    finally:
        db.close()

@dp.message(Command("report"))
async def cmd_report(message: Message):
    if bot is None:
        await message.answer("Bot not configured. Please set BOT_TOKEN environment variable.")
        return
        
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Breakdown by category
        res = db.query(
            Category.name,
            Category.icon,
            Category.type,
            func.sum(Transaction.amount).label("total")
        ).join(
            Transaction, Transaction.category_id == Category.id
        ).filter(
            Transaction.date >= start_month,
            Transaction.archived == False
        ).group_by(Category.name, Category.icon, Category.type).order_by(desc("total")).all()
        
        if not res:
            await message.answer("Belum ada data transaksi bulan ini buat di-breakdown, Bos!", reply_markup=get_main_keyboard())
            return
            
        expenses = [r for r in res if r[2] == "expense"]
        incomes = [r for r in res if r[2] == "income"]
        
        text = f"📑 **Breakdown Kategori ({now.strftime('%B %Y')})**\n\n"
        if expenses:
            text += "🔴 **Pengeluaran:**\n"
            total_exp = sum(r[3] for r in expenses)
            for name, icon, _, total in expenses:
                pct = (total / total_exp * 100) if total_exp > 0 else 0
                text += f"• {icon} {name}: Rp {total:,.0f} ({pct:.1f}%)\n"
            text += "\n"
            
        if incomes:
            text += "🟢 **Pemasukan:**\n"
            for name, icon, _, total in incomes:
                text += f"• {icon} {name}: Rp {total:,.0f}\n"
                
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
    finally:
        db.close()

@dp.message(Command("categories"))
async def cmd_categories(message: Message):
    if bot is None:
        await message.answer("Bot not configured. Please set BOT_TOKEN environment variable.")
        return
    
    db = SessionLocal()
    try:
        categories = db.query(Category).filter(Category.is_active == True).all()
        income_cats = [c for c in categories if c.type == "income"]
        expense_cats = [c for c in categories if c.type == "expense"]
        
        text = "📂 Categories:\n\n"
        text += "💰 Income:\n"
        for cat in income_cats:
            text += f"  {cat.icon} {cat.name}\n"
        
        text += "\n💸 Expenses:\n"
        for cat in expense_cats:
            text += f"  {cat.icon} {cat.name}\n"
            
        await message.answer(text, reply_markup=get_main_keyboard())
    finally:
        db.close()

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    if bot is None:
        await message.answer("Bot not configured. Please set BOT_TOKEN environment variable.")
        return
        
    db = SessionLocal()
    try:
        # Check active non-archived transactions
        count = db.query(Transaction).filter(Transaction.archived == False).count()
        if count == 0:
            await message.answer("ℹ️ Tidak ada transaksi aktif yang perlu di-reset saat ini, Bos!", reply_markup=get_main_keyboard())
            return
            
        # Get totals before reset
        inc = db.query(func.sum(Transaction.amount)).filter(Transaction.type == "income", Transaction.archived == False).scalar() or 0.0
        exp = db.query(func.sum(Transaction.amount)).filter(Transaction.type == "expense", Transaction.archived == False).scalar() or 0.0
        
        # Soft-archive
        db.query(Transaction).filter(Transaction.archived == False).update({Transaction.archived: True})
        db.commit()
        
        text = (
            "🔄 **Bulan Berhasil Di-Reset!**\n\n"
            f"📦 **{count} transaksi** telah diarsipkan ke riwayat bulanan.\n"
            f"💰 Rekap akhir: Masuk `Rp {inc:,.0f}` | Keluar `Rp {exp:,.0f}` | Sisa `Rp {inc-exp:,.0f}`\n\n"
            "✨ Sekarang saldo aktif kembali ke **Rp 0** untuk memulai bulan baru!\n"
            "Riwayat sebelumnya tetap tersimpan rapi di tab/arsip riwayat bulanan web & bot. 🚀"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
    finally:
        db.close()

@dp.message(Command("web"))
@dp.message(F.text == "🌐 Web Dashboard")
async def cmd_web(message: Message):
    if bot is None:
        await message.answer("Bot not configured. Please set BOT_TOKEN environment variable.")
        return
    text = (
        "🌐 **Sky Budget Web Dashboard**\n\n"
        "Klik tombol di bawah ini buat langsung buka web di browser Bos:\n"
        f"🔗 `{PUBLIC_URL}`\n\n"
        "✨ Semua fitur input, grafik breakdown pos, riwayat aktif, dan tombol reset bulanan langsung bisa dipakai di sana!"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_web_button())

# Simple transaction adding (basic implementation)
@dp.message(Command("add_income"))
@dp.message(Command("add_expense"))
async def cmd_add_transaction(message: Message):
    if bot is None:
        await message.answer("Bot not configured. Please set BOT_TOKEN environment variable.")
        return
        
    command = message.text.split()[0][1:]  # Remove '/'
    trans_type = "income" if command == "add_income" else "expense"
    
    await message.answer(
        f"Please enter your {trans_type} transaction in format:\n"
        "Amount Description Category\n"
        "Example: 50000 Groceries Food & Groceries\n\n"
        "Or type /cancel to abort",
        reply_markup=get_main_keyboard()
    )
    
    # Store state for next message (simplified - in production use FSM)
    # For now, we'll just wait for next message and parse it
    # This is a basic implementation - for production use aiogram's FSM

# Simple message handler for transaction input
@dp.message()
async def handle_message(message: Message):
    if bot is None:
        return
        
    text = message.text.strip()
    if text.startswith("/"):
        return  # Let command handlers process commands
    
    # Try to parse as transaction: Amount Description Category
    parts = text.split()
    if len(parts) >= 3:
        try:
            amount = float(parts[0])
            # Find category by name (last part(s))
            # This is simplified - in production you'd want better matching
            category_name = " ".join(parts[2:])
            
            db = SessionLocal()
            try:
                category = db.query(Category).filter(
                    Category.name.ilike(f"%{category_name}%"),
                    Category.is_active == True
                ).first()
                
                if not category:
                    await message.answer(
                        f"Category '{category_name}' not found. "
                        "Please use /categories to see available categories.",
                        reply_markup=get_main_keyboard()
                    )
                    return
                
                # Create transaction
                db_transaction = Transaction(
                    amount=amount,
                    description=" ".join(parts[1:2]) if len(parts) >= 2 else None,
                    category_id=category.id,
                    date=datetime.utcnow(),
                    type=category.type  # income or expense
                )
                db.add(db_transaction)
                db.commit()
                db.refresh(db_transaction)
                
                await message.answer(
                    f"✅ {category.type.capitalize()} recorded!\n"
                    f"Amount: {amount:,.0f}\n"
                    f"Category: {category.icon} {category.name}\n"
                    f"Description: {parts[1] if len(parts) >= 2 else '(none)'}",
                    reply_markup=get_main_keyboard()
                )
            finally:
                db.close()
        except ValueError:
            await message.answer(
                "Invalid format. Please use:\n"
                "Amount Description Category\n"
                "Example: 50000 Groceries Food & Groceries",
                reply_markup=get_main_keyboard()
            )
    elif text == "/cancel":
        await message.answer("Operation cancelled.", reply_markup=get_main_keyboard())
    else:
        # Ignore other messages or show help
        pass

# Main function to run both FastAPI and bot
async def main():
    # Start bot polling if token is configured
    bot_task = None
    if bot is not None:
        print("Starting bot polling...")
        bot_task = asyncio.create_task(dp.start_polling(bot))
    
    # Start FastAPI server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8088,
        log_level="info" if DEBUG else "warning"
    )
    server = uvicorn.Server(config)
    
    # Run both concurrently
    await asyncio.gather(
        server.serve(),
        bot_task if bot_task else asyncio.sleep(0)  # dummy task if no bot
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down budget tracker...")