from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import smtplib
import os
from functools import wraps


EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# # CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# # CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    hashed_password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.String(500), nullable=False)

# with app.app_context():
#     db.create_all()


gravatar = Gravatar(app, size=80, rating='g', default='retro', force_default=False, force_lower=False,
                    use_ssl=False, base_url=None)


# admin only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            if current_user.id != 1:
                return abort(403)
        except AttributeError:
            return redirect(url_for("get_all_posts"))
        else:
            return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter(User.email == form.email.data).first()
        if user:
            flash("That email is already registered. Login instead.")
            return redirect(url_for("login"))
        hashed_pd = generate_password_hash(form.password.data)
        new_user = User(
            email=form.email.data,
            hashed_password=hashed_pd,
            name=form.name.data
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Complete the registration. Please log in.")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(User.email == form.email.data).first()
        if user is None:
            flash("This email is not registered. Please try again.")
            return redirect(url_for("login"))
        elif not check_password_hash(user.hashed_password, form.password.data):
            flash("Password is not correct. Please try again.")
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    comments = Comment.query.filter(Comment.post_id == post_id).all()
    if form.validate_on_submit():
        if current_user.is_authenticated:
            new_comment = Comment(
                author_id=current_user.id,
                post_id=post_id,
                text=form.comment.data
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
        else:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
    return render_template("post.html", post=requested_post, form=form, comments=comments, gravatar=gravatar)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route('/contact', methods=["GET", "POST"])
def contact():
    if request.method == 'POST':
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        message = request.form["message"]
        with smtplib.SMTP("smtp.gmail.com", port=587) as connection:
            connection.starttls()
            connection.login(user=EMAIL, password=PASSWORD)
            connection.sendmail(
                from_addr=EMAIL,
                to_addrs=EMAIL,
                msg=f"Subject:Blog Question!\n\n"
                    f"Name: {name}\n"
                    f"email: {email}\n"
                    f"Phone: {phone}\n"
                    f"Message: {message}".encode("utf-8")
            )
        return render_template("contact.html", msg_sent=True)

    return render_template("contact.html", msg_sent=False)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author_id = current_user.id
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)

