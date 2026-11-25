"""The Terms and Conditions pop-up shown when signing up.

The text lives in TERMS_HTML so it is easy to edit. The dialog is accepted with
"I agree" and rejected with "Close" (or the window's X). Put this file in ui/.
"""
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QTextBrowser,
                               QVBoxLayout)

from core.zoom import px
from ui.theme import COLORS
from ui.widgets import make_button, make_label

_H = f'style="color:{COLORS["primary"]}"'

TERMS_HTML = f"""
<h3 {_H}>1. What cAPIbara is</h3>
<p>cAPIbara is a desktop tool that puts a few handy services in one place:
shortening links, sending texts and emails, keeping a small address book and
generating sample (fake) data. By creating an account you agree to these terms.</p>

<h3 {_H}>2. How it works</h3>
<ul>
<li><b>Your account.</b> You sign up with your name, email, a username and a
password. We email a one-time code to confirm your email before the account is
created. The same kind of code is asked when you change your email or password.
You can log in with either your username or your email.</li>
<li><b>Forgot your username or password?</b> Use the link on the login screen. We
send a one-time code to the email on your account. Once you enter it, your
username is shown and you can set a new password.</li>
<li><b>URL Shortening.</b> The link you enter is sent to a shortening service
(Ulvis first, then is.gd as a backup if the first one fails). The short link is
saved in your history, with a click count kept by this app.</li>
<li><b>SMS and Email.</b> You write a message, choose recipients from your
contacts or type them in, and the app hands it to the sending service.
<b>Emails</b> go out through Brevo from the app's own sender address. Your full
name and email are added at the bottom ("Sent from Your Name &lt;your email&gt;")
and your email is set as the reply address, so the recipient knows who you are
and their reply goes to your own inbox. <b>Texts</b> go out through TextBee from
the phone linked to the app, so the recipient sees that phone's number, not
yours. Unfinished messages can be kept as drafts.</li>
<li><b>Contacts.</b> A personal address book. Each contact has a name and a
mobile number, an email address, or both. Mobile numbers are saved as 09XXXXXXXXX.</li>
<li><b>Fake Data.</b> Random sample people (names, addresses, emails and so on)
are requested from FakerAPI. You choose the fields and how many records. Each
batch is saved as "Gen 1", "Gen 2" and so on.</li>
<li><b>Dashboard.</b> Shows counts of what you have done: emails and texts sent,
links shortened and data batches made, over the last 7 days and all time.</li>
<li><b>Zoom.</b> Ctrl with the mouse wheel, or Ctrl with + / - / 0, changes how big
the app is drawn.</li>
</ul>

<h3 {_H}>3. Limitations</h3>
<ul>
<li><b>Internet is required</b> for shortening links, sending messages, making fake
data and receiving verification codes.</li>
<li><b>Outside services are not ours.</b> Ulvis, is.gd, FakerAPI, TextBee and the
email service can be slow, busy, limit how often you can use them, block a request
or go offline. They can also change how they work. When that happens, the matching
feature may fail until the service is back.</li>
<li><b>Short links belong to the shortening services.</b> They may expire, be
removed or stop working, and we cannot guarantee how long they last.</li>
<li><b>Click counts are local.</b> They only count links you open from inside this
app, not clicks made by other people elsewhere.</li>
<li><b>Texts</b> work for Philippine mobile numbers only (09XXXXXXXXX). They are
sent from the phone linked to the app's TextBee account, so that phone must be on,
online, and have signal and load. The app waits a short time for the phone to
report back. If the phone has not answered by then, the text may still be on its
way, so do not send it again. "Sent" does not promise the message was delivered,
because that depends on the phone, the network and the carrier. TextBee and
Android also limit how many texts can be sent.</li>
<li><b>Emails</b> may arrive late or land in a spam folder. Delivery is not
guaranteed if the sending quota has been reached.</li>
<li><b>cAPIbara can only send, not receive.</b> There is no inbox in the app.
Replies to an email arrive in your own email inbox, and replies to a text go to the
linked phone, so neither can be read in the app.</li>
<li><b>Fake data is not real.</b> The people are randomly generated, are meant for
testing and demos only, and come in batches of 10 to 1000 records.</li>
<li><b>Your data stays on your computer.</b> It is stored in a local file next to the
app, with no cloud backup and no syncing between computers. If that file is deleted
or the computer is lost, the data cannot be recovered.</li>
<li><b>Account recovery needs your email.</b> A forgotten username or password can
only be recovered with a code sent to the email on the account. If you lose access
to that email, the account cannot be recovered.</li>
<li>cAPIbara is not meant for emergencies or for messages where a missed delivery
could cause harm.</li>
</ul>

<h3 {_H}>4. Your account and your data</h3>
<ul>
<li>Your password is never stored as typed. Only a scrambled (salted and hashed)
version is kept.</li>
<li>When you send an email, your full name and email address are added to it
("Sent from ...") and used as its reply address, so the person who receives it
will know who you are and can reply to you directly.</li>
<li>To do their job, the outside services receive what you give them: the link you
shorten, the recipient's phone number or email address, and the message text.
Please do not send anything you are not comfortable passing through them.</li>
<li>Your contacts, links, messages and generated data are tied to your account and
are not shown to other accounts in the app.</li>
</ul>

<h3 {_H}>5. Using the app responsibly</h3>
<ul>
<li>Do not use cAPIbara to send spam, harass anyone, deceive people, or break the
law.</li>
<li>Do not shorten links to harmful, illegal or misleading websites.</li>
<li>Only text or email people who are fine with hearing from you.</li>
<li>Do not use fake data to pretend to be a real person or to submit false
information.</li>
<li>You are responsible for everything you send and for keeping your account
private.</li>
</ul>

<h3 {_H}>6. No warranty</h3>
<p>cAPIbara is provided "as is", without promises that it will always work or be
free of errors. The developers are not responsible for lost data, undelivered
messages, or problems caused by outside services. These terms may change as the
app changes.</p>
"""


class TermsDialog(QDialog):
    """Shows the terms. Accepted = the user clicked "I agree"."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Terms and Conditions")
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(px(580), screen.width() - 20),
                    min(px(640), screen.height() - 60))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(make_label("Terms and Conditions", "heading"))
        layout.addWidget(make_label(
            "Please read how cAPIbara works and what it cannot do.", "muted"))

        body = QTextBrowser()
        body.setOpenExternalLinks(False)
        body.setHtml(TERMS_HTML)
        layout.addWidget(body, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch()
        buttons.addWidget(make_button("Close", self.reject, secondary=True))
        buttons.addWidget(make_button("I agree", self.accept))
        layout.addLayout(buttons)