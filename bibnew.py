#!/usr/bin/env python3
"""
    Este é um bot renovador de livros para o sistema Pergamum da UFBA.

    Para usar basta executar o script (de preferencia todos os dias)
    com as variáveis de ambiente PERGAMUM_LOGIN e PERGAMUM_PASS setadas
    com seu RM e senha da biblioteca.

    Além disso, você pode receber um email sempre que algum evento importante
    ocorre, como a renovação de um livro, a chegada do limite de renovações,
    e até mesmo se ocorrer algum erro no script.

    Para isso, informe nas variáveis de ambinete BIB_EMAIL_TO_ADDR seu
    endereço de email. É necessário também informar BIB_EMAIL_FROM_ADDR e
    BIB_EMAIL_FROM_PASS, que são as credências de algum email qualquer
    do Gmail para ser o remedente do seu email.

    Yes, this is Portuguese mate.

    Copyright (c) 2018 Denilson das Mercês Amorim
    Licensed under the MIT License (https://opensource.org/licenses/MIT)
"""
import os
import re
import sys
import asyncio
import datetime
import logging
from collections import namedtuple
from email.mime.text import MIMEText
from pathlib import Path

import aiohttp
import aiosmtplib
import parsel


PERGAMUM_LOGIN = os.environ['BIB_PERGAMUM_LOGIN']
PERGAMUM_PASS = os.environ['BIB_PERGAMUM_PASS']

BIB_EMAIL_TO_ADDR = os.environ.get('BIB_EMAIL_TO_ADDR')
if BIB_EMAIL_TO_ADDR is not None:
    BIB_EMAIL_FROM_ADDR = os.environ['BIB_EMAIL_FROM_ADDR']
    BIB_EMAIL_FROM_PASS = os.environ['BIB_EMAIL_FROM_PASS']

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stderr, level=logging.INFO,
        format=('[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - '
                f'{PERGAMUM_LOGIN} - %(message)s'))

BIB_URL = 'http://www.pergamum.bib.ufba.br'

BIB_MAX_RENEW = 7

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:57.0) Gecko/20100101 Firefox/57.0',
}

Book = namedtuple('Book', 'name return_date renew_count cod_acervo cod_exemplar')


def list_books(books):
    """Creates a string that, on each line, informs about a book."""
    return '\n'.join([f'+ {book.name}: {book.renew_count}: {book.return_date}'
                      for book in books])

def extract_books(html):
    """Yields a sequence of all books in the HTML."""
    selector = parsel.Selector(html)
    for li in selector.xpath('/html/body/div[1]/div[2]/ul/li'):
        if li.xpath('./@data-role').extract_first() == 'list-divider':
            continue
        if li.xpath('count(./*)').extract_first() == '0.0':
            continue
        a = li.xpath('.//a')

        ahref = a.xpath('./@href').extract_first()
        h2 = a.xpath('normalize-space(./h2)').extract_first()
        p1 = a.xpath('normalize-space(./p[1])').extract_first()
        p2 = a.xpath('normalize-space(./p[2])').extract_first()

        book_name = h2.strip()

        return_date = p1.split(':', maxsplit=1)[1].strip()
        return_date = datetime.datetime.strptime(return_date, '%d/%m/%Y').date()

        renew_count = p2.split(':', maxsplit=1)[1].strip()
        renew_count = int(renew_count)

        cod_acervo = int(re.search(r'cod_acervo=(\d+)', ahref).group(1))
        cod_exemplar = int(re.search(r'cod_exemplar=(\d+)', ahref).group(1))

        yield Book(book_name, return_date, renew_count, cod_acervo, cod_exemplar)

async def pergamum_login(session):
    """Logins the web session into the pergamum system."""
    login_url = '/'.join([BIB_URL, 'pergamum/mobile/login.php'])
    data = {
        'flag': 'renovacao.php',
        'login': PERGAMUM_LOGIN,
        'password': PERGAMUM_PASS,
        'button': 'Acessar'
    }
    headers = {
        'Referer': f'{login_url}?flag=renovacao.php'
    }
    return await session.post(login_url, headers=headers, data=data)

async def pergamum_renovacao_page(session):
    renovacao_url = '/'.join([BIB_URL, 'pergamum/mobile/renovacao.php'])
    return await session.get(renovacao_url)

async def pergamum_renew(session, book):
    """Renews a book in the specified web session."""
    params = {'cod_acervo': book.cod_acervo, 'cod_exemplar': book.cod_exemplar}
    renovar_url = '/'.join([BIB_URL, 'pergamum/mobile/confirmar_renovacao.php'])
    return await session.get(renovar_url, params=params)

async def email_send(subject, text):
    """Sends an email with the specified subject and text.
    
    The email is sent from an email specified in environ and into a
    email also specified in environment variables.
    
    If the environment variables are missing, no email is sent."""
    if BIB_EMAIL_TO_ADDR is None:
        return
    smtp = aiosmtplib.SMTP(hostname='smtp.gmail.com', port=587)
    await smtp.connect()
    try:
        await smtp.starttls()
        await smtp.login(BIB_EMAIL_FROM_ADDR, BIB_EMAIL_FROM_PASS)
        message = MIMEText(text)
        message['From'] = BIB_EMAIL_FROM_ADDR
        message['To'] = BIB_EMAIL_TO_ADDR
        message['Subject'] = subject
        await smtp.send_message(message)
    finally:
        await smtp.quit()

async def main():
    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        # For some reason anything but portuguese works correctly.
        session.cookie_jar.update_cookies({'idioma_mobile_pessoal': 6})

        renew_books = []
        due_books = []
        email_tasks = []

        today = datetime.datetime.now().date()
        response = await pergamum_login(session)
        books = list(extract_books(await response.text()))
        for book in books:
            if book.return_date == today:
                renew_books.append(book)
            elif book.return_date < today:
                due_books.append(book)

        renewed_books = []
        failed_books = []

        completed = await asyncio.gather(*[pergamum_renew(session, book) 
                                           for book in renew_books],
                                         return_exceptions=True)

        response = await pergamum_renovacao_page(session)
        current_books = list(extract_books(await response.text()))

        for book, result in zip(renew_books, completed):
            if isinstance(result, Exception):
                logging.error(f"Falhar ao renovar livro {book.name}: {str(result)}")
                failed_books.append(book)
            elif book in current_books:
                logging.error(f"Falha ao renovar livro {book.name}: Estado do livro não foi alterado!")
                Path(f"~/bibnew-{book.book_name}.html").write_text(await result.text())
                failed_books.append(book)
            else:
                renewed_books.append(book)

        if len(due_books) > 0:
            logging.info(f'Há {len(due_books)} livros vencidos, enviando email.')
            msg = 'Os seguintes livros passaram da data de renovação:\n'
            msg += list_books(due_books)
            coro = email_send('Livros vencidos!', msg)
            email_tasks.append(coro)

        if len(failed_books) > 0:
            logging.info(f'Há {len(failed_books)} livros falhados, enviando email.')
            msg = 'Os seguintes livros falharam a ser renovados:\n'
            msg += list_books(failed_books)
            msg += '\n\nPor favor informe ao administrador do bot.'
            coro = email_send('Livros falharam!', msg)
            email_tasks.append(coro)

        if len(renewed_books) > 0:
            logging.info(f'Um total de {len(renewed_books)} livros foram'
                         f' renovados com sucesso.')
            on_limit = [b for b in renewed_books if b.renew_count+1 == BIB_MAX_RENEW]
            subject = ('Livros renovados, mas cuidado!' if on_limit 
                        else 'Livros renovados com sucesso.')
            msg = 'Os seguintes livros foram renovados:\n'
            msg += list_books(renewed_books)
            if on_limit:
                msg += ('\nNo entanto os seguintes livros não poderão ser renovados na'
                        ' próxima semana! É necessário intervenção pessoal.\n')
                msg += list_books(on_limit)
            coro = email_send(subject, msg)
            email_tasks.append(coro)

        if len(email_tasks) == 0:
            logging.info(f'Foram encontrados {len(books)} livros mas nenhuma ação'
                         f' precisa ser tomada.')

        await asyncio.gather(*email_tasks)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except Exception:
        logger.exception("Erro fatal")
        coro = email_send('Erro fatal no renovador de livros!',
                f'Por favor, informe ao administrador, um erro fatal ocorreu durante'
                f' o processo de verificação e renovação automatica de livros.')
        loop.run_until_complete(coro)
    finally:
        loop.close()

