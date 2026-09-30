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
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./budget.db")
BOT_TOKEN = os.getenv("BOT_TOKEN", "123456:TEST_TOKEN")  # Will need real token for production
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

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
    query = db.query(Transaction)
    if type:
        query = query.filter(Transaction.type == type)
    return query.offset(skip).limit(limit).all()

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
        Transaction.date <= end_dt
    )
    expense_query = select(func.sum(Transaction.amount)).where(
        Transaction.type == "expense",
        Transaction.date >= start_dt,
        Transaction.date <= end_dt
    )
    count_query = select(func.count(Transaction.id)).where(
        Transaction.date >= start_dt,
        Transaction.date <= end_dt
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
    builder.add(KeyboardButton(text="/add_income"))
    builder.add(KeyboardButton(text="/add_expense"))
    builder.add(KeyboardButton(text="/stats"))
    builder.add(KeyboardButton(text="/categories"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Bot handlers
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "💰 Welcome to Budget Tracker Bot!\n\n"
        "I can help you track your income and expenses.\n"
        "Use the buttons below or type commands:\n"
        "/add_income - Add income transaction\n"
        "/add_expense - Add expense transaction\n"
        "/stats - View monthly statistics\n"
        "/categories - View categories\n"
        "/help - Show help",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📋 Budget Tracker Help:\n\n"
        "💰 /add_income - Add income\n"
        "💸 /add_expense - Add expense\n"
        "📊 /stats - View statistics\n"
        "📂 /categories - View categories\n"
        "\nWhen adding transactions, please provide:\n"
        "Amount Description Category\n"
        "Example: 50000 Groceries Food & Groceries",
        reply_markup=get_main_keyboard()
    )

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