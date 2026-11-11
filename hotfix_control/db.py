import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='tecnico')
    active = Column(Integer, nullable=False, default=1)

class Machine(Base):
    __tablename__ = 'machines'
    id = Column(Integer, primary_key=True)
    hostname = Column(String(150), unique=True, nullable=False)
    ip = Column(String(64), default='')
    network = Column(String(30), nullable=False)
    responsible = Column(String(150), default='')
    contact = Column(String(200), default='')
    notes = Column(Text, default='')
    active = Column(Integer, default=1)

class Campaign(Base):
    __tablename__ = 'campaigns'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class Patch(Base):
    __tablename__ = 'patches'
    __table_args__ = (UniqueConstraint('campaign_id','machine_id',name='uq_campaign_machine'),)
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey('campaigns.id'), nullable=False)
    machine_id = Column(Integer, ForeignKey('machines.id'), nullable=False)
    status = Column(String(80), default='Pendiente')
    method = Column(String(30), default='Manual')
    kb = Column(String(100), default='')
    patch_month = Column(String(30), default='')
    technician = Column(String(100), default='')
    notes = Column(Text, default='')
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), default=utcnow)

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    patch_id = Column(Integer, ForeignKey('patches.id'), nullable=False)
    actor = Column(String(100), nullable=False)
    old_status = Column(String(80), default='')
    new_status = Column(String(80), default='')
    comment = Column(Text, default='')
    created_at = Column(DateTime(timezone=True), default=utcnow)

url = os.getenv('DATABASE_URL', '')
if not url:
    try:
        import streamlit as st
        url = st.secrets.get('DATABASE_URL', '')
    except Exception:
        pass
if not url:
    raise RuntimeError('Configura DATABASE_URL con una base de datos PostgreSQL. No se utiliza SQLite para evitar pérdida de datos en despliegues compartidos.')
engine = create_engine(url, pool_pre_ping=True)
Session = sessionmaker(bind=engine, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(engine)
