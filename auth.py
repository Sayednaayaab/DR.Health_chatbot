from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
import os
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@auth_bp.route('/register')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('register.html')

@auth_bp.route('/manual_login', methods=['POST'])
def manual_login():
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        user = User.query.filter_by(email=email).first()
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password')
            return redirect(url_for('auth.login'))
    except Exception as e:
        print(f"Error in manual_login: {e}")
        flash('An error occurred during login')
        return redirect(url_for('auth.login'))

@auth_bp.route('/manual_register', methods=['POST'])
def manual_register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('auth.register'))

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error in manual_register: {e}")
        flash('An error occurred during registration')
        return redirect(url_for('auth.register'))



@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@auth_bp.route('/google_login')
def google_login():
    from app import google
    redirect_uri = url_for('auth.google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@auth_bp.route('/google_callback')
def google_callback():
    from app import google
    try:
        token = google.authorize_access_token()
        user_info = google.parse_id_token(token)

        email = user_info['email']
        name = user_info.get('name', email.split('@')[0])

        # Check if user exists
        user = User.query.filter_by(email=email).first()
        if not user:
            # Create new user for OAuth
            user = User(name=name, email=email)
            db.session.add(user)
            db.session.commit()

        login_user(user)
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Google OAuth error: {e}")
        flash('Google login failed. Please try again.')
        return redirect(url_for('auth.login'))
