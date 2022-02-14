from config import settings
from datetime import datetime
import json
import redis
import logging
import traceback
import secrets
import os
from urllib.parse import urlparse


from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

# Enable logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

# Redis

r = redis.Redis(host=settings.ratelimit.token_redis.endpoint, port=settings.ratelimit.token_redis.port, decode_responses=True)

# Token management

class TokenModel:
    def __init__(self, token: str, telegram_user_id: str, description: str, ips: list, domains: list):
        self.token = token
        self.telegram_user_id = telegram_user_id
        self.description = description
        self.ips = ips
        self.domains = domains

def get_user_token(telegram_user_id: str) -> TokenModel:
    token = r.get(telegram_user_id)
    token_data = json.loads(r.get(token))
    return TokenModel(token, token_data['telegram_user_id'], token_data['description'], token_data['ips'], token_data['domains'])

def user_has_token(telegram_user_id: str) -> bool:
    return r.exists(telegram_user_id) > 0

def create_token(telegram_user_id: str, telegram_user_name: str, description: str, ips: list, domains: list) -> TokenModel:
    token = secrets.token_hex(32)
    record = {
        'create_timestamp': datetime.utcnow().timestamp(),
        'telegram_user_id': telegram_user_id,
        'telegram_user_name': telegram_user_name,
        'description': description,
        'ips': ips,
        'domains': domains,
        'version': 1,
        'limits': {}
    }
    p = r.pipeline()
    p.set(token, json.dumps(record))
    p.set(telegram_user_id, token)
    p.execute()

    return TokenModel(token, telegram_user_id, description, ips, domains)

def delete_token(telegram_user_id: str) -> None:
    token = r.get(telegram_user_id)
    p = r.pipeline()
    p.delete(token)
    p.delete(telegram_user_id)    
    p.execute()

# Helper functions

def validate_ip(s):
    a = s.split('.')
    if len(a) != 4:
        return False
    for x in a:
        if not x.isdigit():
            return False
        i = int(x)
        if i < 0 or i > 255:
            return False
    return True

def normalize_domain(s):
    parsed = urlparse(s)
    if 'http' not in parsed.scheme:
        return None
    if not parsed.hostname:
        return None
    return f'{parsed.scheme}://{parsed.hostname}'

# Telegram Bot states

ACTION, PROJECT_DESCRIPTION, REVOKE_CONFIRMATION, LIMIT_CLIENT_IP, LIMIT_CLIENT_DOMAINS = range(5)

def start(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    if user_has_token(str(update.message.from_user.id)):
        reply_keyboard = [['My API Token', 'Revoke My API Token']]
    else:
        reply_keyboard = [['Create API Token']]
    update.message.reply_text(
        f"{os.getenv('MAIN_DOMAIN')} API token management bot. How can I help?",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        ),
    )

    return ACTION

def my_api_token(update: Update, context: CallbackContext) -> int:
    logger.info(f"User {update.message.from_user.id} wants to get their token")
    try:
        token_model = get_user_token(str(update.message.from_user.id))
    except Exception:
        logger.error(f"Exception while fetching user's token: {traceback.format_exc()}")
        update.message.reply_text("Oops, error occured while fetching your token. Try again later.")
        return ConversationHandler.END

    response = f"""Your API token: `{token_model.token}`
Allowed IPs: `{' '.join(token_model.ips) if len(token_model.ips) else 'any'}`
Allowed domains: `{' '.join(token_model.domains) if len(token_model.domains) else 'any'}`
"""
    update.message.reply_markdown(
        response, reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

def revoke_my_api_token(update: Update, context: CallbackContext) -> int:
    logger.info(f"User {update.message.from_user.id} wants to revoke their token")
    reply_keyboard = [['Yes, I confirm to revoke my API token', 'Cancel']]
    update.message.reply_text("Do you confirm to revoke you API token? All requests with it will fail after revoking.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        )
    )
    return REVOKE_CONFIRMATION

def revoke_confirmation(update: Update, context: CallbackContext) -> int:
    try:
        delete_token(str(update.message.from_user.id))
    except Exception:
        logger.error(f"Exception while revoking token: {traceback.format_exc()}")
        update.message.reply_text("Oops, error occured while revoking token. Try again later.")
        return ConversationHandler.END

    logger.info(f"User {update.message.from_user.id} has revoked their token")
    update.message.reply_text("Your API token has been revoked.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def create_api_token(update: Update, context: CallbackContext) -> int:
    if user_has_token(str(update.message.from_user.id)):
        logger.info(f"User {update.message.from_user.id} tried to create existing token")
        update.message.reply_text('You already have a token')
        return ConversationHandler.END

    logger.info(f"User {update.message.from_user.id} started token creation")
    reply_keyboard = [['Cancel']]
    update.message.reply_text("Sure, let's create one. Please, tell me about your project.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        )
    )
    return PROJECT_DESCRIPTION

def project_description(update: Update, context: CallbackContext) -> int:
    description = update.message.text
    if len(description.strip()) == 0:
        logger.info(f"User {update.message.from_user.id} sent short description.")
        update.message.reply_text("Please enter non-empty description.")
        return PROJECT_DESCRIPTION

    context.user_data['description'] = description

    reply_keyboard = [['Do not restrict by IP']]
    update.message.reply_text(f"Do you want to restrict usage of your API key to specific IPs? If yes, send a list of IPs separated by space.\n{os.getenv('MAIN_DOMAIN')} will reject requests from any other IP with your token.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        )
    )

    return LIMIT_CLIENT_IP

def limit_client_ip(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Do not restrict by IP':
        context.user_data['ips'] = []
    else:
        ips = update.message.text.split()
        if all(map(validate_ip, ips)):
            context.user_data['ips'] = ips
        else:
            logger.info(f"User {update.message.from_user.id} input incorrect IPs: {update.message.text}")
            reply_keyboard = [['Do not restrict by IP']]
            update.message.reply_text("Error parsing IP addresses. Please, try again.",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True
                )
            )
            return LIMIT_CLIENT_IP

    reply_keyboard = [['Do not restrict by origin domains']]
    update.message.reply_markdown("Do you want to restrict usage of your API key to specific domains? If yes, send a list of domains separated by space. \nExample: `https://ton.org https://ton.sh`\nThese domains will be set as CORS allowed domains for your token.",
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, one_time_keyboard=True
        )
    )

    return LIMIT_CLIENT_DOMAINS

def limit_client_domains(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Do not restrict by origin domains':
        context.user_data['domains'] = []
    else:
        domains = update.message.text.split()
        normalized_domains = list(map(normalize_domain, domains))
        if all(normalized_domains):
            context.user_data['domains'] = normalized_domains
        else:
            logger.info(f"User {update.message.from_user.id} input incorrect domains: {update.message.text}")
            reply_keyboard = [['Do not restrict by origin domains']]
            update.message.reply_text("Error parsing domains. Please, try again.",
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True
                )
            )
            return LIMIT_CLIENT_DOMAINS

    try:
        token_model = create_token(update.message.from_user.id, update.message.from_user.name, context.user_data['description'], context.user_data['ips'], context.user_data['domains'])
    except Exception as e:
        logger.error(f"Exception while creating token: {traceback.format_exc()}")
        update.message.reply_text("Oops, error occured while creating token. Try again later.")
        return ConversationHandler.END

    logger.info(f"User {update.message.from_user.id} created token {token_model.token} with data: {context.user_data}")
    update.message.reply_markdown(f"Here's your API token: `{token_model.token}`", 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    logger.info(f"User {update.message.from_user.id} canceled the conversation.")
    update.message.reply_text(
        'Bye!', reply_markup=ReplyKeyboardRemove()
    )

    return ConversationHandler.END

def main() -> None:
    password_file = settings.ratelimit.token_bot.token_file
    with open(password_file, 'r') as f:
        token = f.read()
    updater = Updater(token)

    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.all, start)],
        states={
            ACTION: [
                MessageHandler(Filters.regex('^My API Token$'), my_api_token),
                MessageHandler(Filters.regex('^Revoke My API Token$'), revoke_my_api_token),
                MessageHandler(Filters.regex('^Create API Token$'), create_api_token)
            ],
            REVOKE_CONFIRMATION: [MessageHandler(Filters.regex('^Yes, I confirm to revoke my API token$') & ~Filters.regex('^Cancel$'), revoke_confirmation)],
            PROJECT_DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command & ~Filters.regex('^Cancel$'), project_description)],
            LIMIT_CLIENT_IP: [MessageHandler(Filters.text & ~Filters.command & ~Filters.regex('^Cancel$'), limit_client_ip)],
            LIMIT_CLIENT_DOMAINS: [MessageHandler(Filters.text & ~Filters.command & ~Filters.regex('^Cancel$'), limit_client_domains)],
        },
        fallbacks=[MessageHandler(Filters.regex('^Cancel$'), cancel)],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
