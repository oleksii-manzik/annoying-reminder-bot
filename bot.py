import logging
import signal
from telegram.ext import Updater, CommandHandler, MessageHandler
from telegram import InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import Unauthorized
from random import choice, randint

from scripts.my_filters import UserSpeciesFilter, TaskFilter, StopFilter, StartFilter, ChangeSpecies, ChangeTask, ChangeAll, NotChangingFilter
from scripts.strings import TOKEN, MESSAGE_QUEUE, USER_SPECIES, REMINDERS, STOP_MESSAGE, START_MESSAGE, CHANGE_DATA_ANSWERS
from scripts.databaser import insert_chat_id, update_species, update_task, select_species_and_task, delete_reminder, insert_ongoing_processes, select_ongoing_processes, delete_ongoing_process

logging.basicConfig(format='%(asctime)s - %(levelname)s - {%(lineno)d:%(filename)s} - %(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S',
                    level='INFO')
logger = logging.getLogger(__name__)


def start(bot, update):
    """Invokes by /start and START_MESSAGE"""

    chat_id = update.message.chat_id

    # check if there is already job for user and if so remove it
    existed_job = job_queue.get_jobs_by_name(chat_id)
    if len(existed_job) > 0:
        for i in range(len(existed_job)):
            job_queue.get_jobs_by_name(chat_id)[i].schedule_removal()

    # check if user is already in db
    db_species_and_task = select_species_and_task(chat_id)

    # for new user
    if len(db_species_and_task) == 0:
        logger.info(f'{chat_id} is new user and start conversation')
        keyboard = [
            [InlineKeyboardButton(USER_SPECIES[0])],
            [InlineKeyboardButton(USER_SPECIES[1])],
            [InlineKeyboardButton(USER_SPECIES[2])]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        # at first ask about user species
        bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[0], reply_markup=reply_markup)

    # for old user
    else:
        logger.info(f'{chat_id} is old user and start conversation')
        keyboard = [
            [InlineKeyboardButton(CHANGE_DATA_ANSWERS[0]), InlineKeyboardButton(CHANGE_DATA_ANSWERS[1])],
            [InlineKeyboardButton(CHANGE_DATA_ANSWERS[2]), InlineKeyboardButton(CHANGE_DATA_ANSWERS[3])]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        # ask if user want to change anything or run as it is
        bot.send_message(chat_id=chat_id,
                         text=f"{MESSAGE_QUEUE[4][0]} {db_species_and_task[0]} {MESSAGE_QUEUE[4][1]} {db_species_and_task[1]}{MESSAGE_QUEUE[4][2]}",
                         reply_markup=reply_markup)


def receive_user_species(bot, update):
    """Invokes by one of the USER_SPECIES element"""

    chat_id = update.message.chat_id
    species = update.message.text

    # if it is first time for specific chat_id to use this bot
    # or user wants to change species it will only insert new chat_id
    # and if not - it will return species and task from db
    species_and_task = insert_chat_id(chat_id)

    # update species for chat_id
    update_species(chat_id, species)

    if species_and_task is None:
        # if user new or want to change everything it will ask about task
        bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[1], reply_markup=ReplyKeyboardRemove())
        logger.info(f'{chat_id} set species. Now user need to set task')
    else:
        # if it is old user which only wants to change own species
        # it will set job
        set_job(chat_id)
        logger.info(f'job for {chat_id} has been set in receive_user_species()')
        bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[2], reply_markup=ReplyKeyboardRemove())


def receive_task(bot, update):
    """Invokes by any text which is not specific command"""

    chat_id = update.message.chat_id
    task = update.message.text

    # change task in db
    update_task(chat_id, task)

    # set job to job_queue
    set_job(chat_id)
    logger.info(f'job for {chat_id} has been set in receive_task()')
    bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[2], reply_markup=ReplyKeyboardRemove())


def set_job(chat_id):
    """Uses for setting jobs"""

    interval = randint(1, 15) * 60
    job_queue.run_repeating(send_remind, interval=interval, context=chat_id, name=chat_id)


def send_remind(bot, job):
    """Func which is called by job_queue.run_repeating()"""

    chat_id = job.context
    new_interval = randint(1, 15) * 60

    # changing interval for job
    job.interval = new_interval

    # get species and task from db
    species, task = select_species_and_task(chat_id)

    # init reminders_list for user species
    reminders_list = [*REMINDERS[species], *REMINDERS['Без роду']]
    random_question = choice(reminders_list)

    # questions can have task in different place in string
    # so it needs to be separated to create message
    if random_question[-1] == 'LEFT':
        text = f'{random_question[0]} {task}'
    elif random_question[-1] == 'RIGHT':
        text = f'{task} {random_question[0]}'
    else:  # if equals 'CENTER'
        text = f'{random_question[0][0]} {task} {random_question[0][1]}'

    keyboard = [[InlineKeyboardButton(STOP_MESSAGE)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    # check if user blocked bot
    try:
        bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        logger.info(f'for {chat_id} was sent reminder: {text}')
    # remove job from job_queue if user blocked bot
    except Unauthorized:
        job.schedule_removal()
        logger.info(f'job for {chat_id} was stopped because user has blocked bot')


def stop(bot, update):
    """Invokes by STOP_MESSAGE"""

    chat_id = update.message.chat_id

    # removing job from job_queue if user wants to stop
    existed_jobs = job_queue.get_jobs_by_name(chat_id)
    if len(existed_jobs) > 0:
        for i in range(len(existed_jobs)):
            job_queue.get_jobs_by_name(chat_id)[i].schedule_removal()
    logger.info(f'{chat_id} has stopped job by STOP_MESSAGE')

    # remove job from ongoing_processes table if job in it
    ongoing_processes = select_ongoing_processes()
    if chat_id in ongoing_processes:
        delete_ongoing_process(chat_id)

    # sending START_MESSAGE which invokes /start
    keyboard = [[InlineKeyboardButton(START_MESSAGE)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[3], reply_markup=reply_markup)


def start_message(bot, update):
    """Handles START_MESSAGE"""
    start(bot, update)
    logger.info(f'{update.message.chat_id} has started conversation with START_MESSAGE')


def change_species(bot, update):
    """Handles situation if user wants to change only species"""

    chat_id = update.message.chat_id
    keyboard = [
        [InlineKeyboardButton(USER_SPECIES[0])],
        [InlineKeyboardButton(USER_SPECIES[1])],
        [InlineKeyboardButton(USER_SPECIES[2])]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[0], reply_markup=reply_markup)
    logger.info(f'{chat_id} wanted to change species')


def change_task(bot, update):
    """Handles situation if user wants to change only task"""

    chat_id = update.message.chat_id
    bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[1], reply_markup=ReplyKeyboardRemove())
    logger.info(f'{chat_id} wanted to change task')


def change_all(bot, update):
    """Handles situation if user wants to change all"""

    chat_id = update.message.chat_id

    # it needs to delete all data about user so
    # receive_user_species and receive_task funcs
    # will offer user to change species and task
    delete_reminder(chat_id)

    # run /start as for new user now
    start(bot, update)
    logger.info(f'{chat_id} has started conversation with change_all()')


def not_changing(bot, update):
    """Handles situation if user doesn't want to change anything"""

    chat_id = update.message.chat_id

    # just setting job with old data from db
    set_job(chat_id)
    logger.info(f'job for {chat_id} has been set in not_changing()')

    bot.send_message(chat_id=chat_id, text=MESSAGE_QUEUE[2], reply_markup=ReplyKeyboardRemove())


def handle_dyno_restart(signal, frame):
    """Invokes when SIGTERM is sent"""

    logger.info('dyno is restarting...')

    # get all current jobs
    jobs = job_queue.jobs()

    # excluding jobs which are gonna be removed
    jobs = [x.name for x in jobs if not x.removed]

    if len(jobs) > 0:

        # inserting to ongoing_processes table name of job
        # which is chat_id
        insert_ongoing_processes(jobs)
    else:
        logger.info('No jobs were inserted to ongoing_processes table because there are no current jobs')

    updater.stop()


def check_ongoing_processes():
    """Checking for ongoing_processes in db table. If there are
    it is setting jobs for these chat_ids"""

    ongoing_processes = select_ongoing_processes()

    if len(ongoing_processes) > 0:
        for chat_id in ongoing_processes:
            set_job(chat_id)
            logger.info(f'job for {chat_id} has been set in check_ongoing_processes()')
    else:
        logger.info('There are no ongoing processes for now')


def main():
    global updater
    updater = Updater(token=TOKEN)
    dispatcher = updater.dispatcher
    global job_queue
    job_queue = updater.job_queue
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(UserSpeciesFilter(), receive_user_species))
    dispatcher.add_handler(MessageHandler(TaskFilter(), receive_task))
    dispatcher.add_handler(MessageHandler(StopFilter(), stop))
    dispatcher.add_handler(MessageHandler(StartFilter(), start_message))
    dispatcher.add_handler(MessageHandler(ChangeSpecies(), change_species))
    dispatcher.add_handler(MessageHandler(ChangeTask(), change_task))
    dispatcher.add_handler(MessageHandler(ChangeAll(), change_all))
    dispatcher.add_handler(MessageHandler(NotChangingFilter(), not_changing))

    updater.start_polling(clean=True)


if __name__ == '__main__':
    main()

    # checking if before dyno restart there were running jobs
    check_ongoing_processes()

    # handling dyno restart
    signal.signal(signal.SIGTERM, handle_dyno_restart)
