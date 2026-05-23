"""SQLite schema for Ma:Vi."""

from __future__ import annotations


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  public_key TEXT,
  avatar_path TEXT,
  status TEXT DEFAULT 'offline',
  last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  last_login DATETIME
);

CREATE TABLE IF NOT EXISTS user_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,
  public_key TEXT NOT NULL,
  encrypted_private_key TEXT,
  key_fingerprint TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  contact_id INTEGER NOT NULL,
  nickname TEXT,
  favorite BOOLEAN DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(contact_id) REFERENCES users(id),
  UNIQUE(user_id, contact_id)
);

CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user1_id INTEGER NOT NULL,
  user2_id INTEGER NOT NULL,
  last_message_id INTEGER,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user1_id) REFERENCES users(id),
  FOREIGN KEY(user2_id) REFERENCES users(id),
  UNIQUE(user1_id, user2_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id INTEGER NOT NULL,
  sender_id INTEGER NOT NULL,
  receiver_id INTEGER NOT NULL,
  content TEXT NOT NULL,
  message_type TEXT DEFAULT 'text',
  nonce TEXT,
  tag TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  delivered BOOLEAN DEFAULT 0,
  read BOOLEAN DEFAULT 0,
  FOREIGN KEY(conversation_id) REFERENCES conversations(id),
  FOREIGN KEY(sender_id) REFERENCES users(id),
  FOREIGN KEY(receiver_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER,
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_size INTEGER,
  file_type TEXT,
  checksum TEXT,
  encrypted_file BOOLEAN DEFAULT 0,
  original_file_name TEXT,
  plaintext_checksum TEXT,
  status TEXT DEFAULT 'offered',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  caller_id INTEGER NOT NULL,
  callee_id INTEGER NOT NULL,
  status TEXT DEFAULT 'ringing',
  start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  end_time DATETIME,
  duration INTEGER,
  FOREIGN KEY(caller_id) REFERENCES users(id),
  FOREIGN KEY(callee_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  token TEXT UNIQUE NOT NULL,
  refresh_token TEXT UNIQUE NOT NULL,
  expires_at DATETIME NOT NULL,
  refresh_expires_at DATETIME NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS login_attempts (
  username TEXT PRIMARY KEY,
  failed_count INTEGER DEFAULT 0,
  first_failed_at DATETIME,
  locked_until DATETIME
);

CREATE TABLE IF NOT EXISTS search_cache (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  query TEXT NOT NULL,
  results TEXT NOT NULL,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""
