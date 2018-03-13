# BIBNEW - Renewing Books on Pergamum

You had a nice but tiring day. It's finally time to forget everything and sleep. You wake up the next morning and you remember: You forgot to renew that book. Yes, that book you are going to use for next week's exams.

Renewing books... Why do we even have to do this?

It makes no sense. That is why I made this bot. This little boy will go into UFBA's Pergamum System, check books that need reneweing and do it all automatically. Once you run this in a cron every day, you'll no longer need to worry about books. It should also work well on other Pergamum Systems with minimal changes.

The bot will also send you emails whenever it renews a book, whether you are near the renewing limit, and all that nice cheese. It also emails in case of failure.

## Usage

First of all, install the bot dependencies using [Pipenv](https://docs.pipenv.org/):

    $ pipenv install
   
Then you need to set a few environment variables:

 + `BIB_PERGAMUM_LOGIN`: Your Pergamum Login.
 + `BIB_PERGAMUM_PASS`: Your Pergamum Password.
 
And optionally, for email support:

 + `BIB_EMAIL_TO_ADDR`: The email address that should receive the emails.
 + `BIB_EMAIL_FROM_ADDR`: An email must be send from another email, right? This is the email to send from. Must be Gmail
 + `BIB_EMAIL_FROM_PASS`: The password of the sender. Of course, this email should be a dummy email.

Then you may run the script, like this:

    $ pipenv run python bibnew.py

Ideally this should be run in a cron every day. It renews only when it really needs to, so it may be a NO-OP during a few days.

## License

It's MIT. Yes! Fork it! Stop the book oppression on your college too!

