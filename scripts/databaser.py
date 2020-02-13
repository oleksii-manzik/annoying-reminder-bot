import os
import logging
import psycopg2

from .strings import USER, HOST, PASSWORD, DATABASE

# True if using credential to access db
# False if running on heroku and using DATABASE_URL
MANUAL = True

logger = logging.getLogger(__name__)


def insert_chat_id(chat_id):
    """If chat_id is new for db then it will insert row with this chat_id
    as primary_key and default values for species and task columns"""

    # at first we need to check if this chat_id is already in db
    species_and_task = select_species_and_task(chat_id)

    # if no - insert it
    if len(species_and_task) == 0:
        INSERT_SPECIES_QUERY = """INSERT INTO reminder (chat_id, species, task)
                            VALUES
                            ((%s),'None','Завдання не назначено')"""
        _run_query(INSERT_SPECIES_QUERY, chat_id)
        logger.info(f'{chat_id} wasn\'t at db so the new row was added')

    # if yes - return species and task
    else:
        logger.info(f'{chat_id} is already in db so insert_chat_id() returns species and task')
        return species_and_task


def update_species(chat_id, species):
    """Update species for chat_id"""

    UPDATE_SPECIES_QUERY = """UPDATE reminder 
                            SET species = '(%s)'
                            WHERE chat_id = (%s)"""
    _run_query(UPDATE_SPECIES_QUERY, species, chat_id)
    logger.info(f'{chat_id} has updated species to {species}')


def update_task(chat_id, task):
    """Update task for chat_id"""

    UPDATE_TASK_QUERY = """UPDATE reminder 
                        SET task = (%s)
                        WHERE chat_id = (%s)"""
    _run_query(UPDATE_TASK_QUERY, task, chat_id)
    logger.info(f'{chat_id} has updated task to {task}')


def select_species_and_task(chat_id):
    """Return species and task for chat_id"""

    SELECT_SPECIES_AND_TASK_QUERY = """SELECT species, task FROM reminder
                                    WHERE chat_id = (%s)"""
    species_and_task = _run_query(SELECT_SPECIES_AND_TASK_QUERY, chat_id)
    species_and_task = species_and_task[0] if len(species_and_task) > 0 else species_and_task
    return species_and_task


def delete_reminder(chat_id):
    """Delete row for chat_id in reminder table"""

    DELETE_REMINDER_QUERY = """DELETE FROM reminder
                        WHERE chat_id = (%s)"""
    _run_query(DELETE_REMINDER_QUERY, chat_id)
    logger.info(f'{chat_id} was deleted from reminder table')


def insert_ongoing_processes(chat_ids):
    """
    Takes chat_ids of current jobs and compare it with jobs from ongoing_processes
    table. Then insert new chat_ids.
    :param chat_ids: current jobs
    :return: None
    """

    ongoing_processes_from_db = select_ongoing_processes()

    # set() is used for situation when one user has set many jobs with START_MESSAGE
    # but it is not normal and with adequate users that will not happen
    chat_ids = set([chat_id for chat_id in chat_ids if chat_id not in ongoing_processes_from_db])

    if len(chat_ids) > 0:
        for chat_id in chat_ids:
            _run_query(
                """INSERT INTO ongoing_processes (chat_id)
                VALUES ((%s))""", chat_id
            )
            logger.info(f'{chat_id} was inserted to ongoing_processes')
    else:
        logger.info('No jobs were inserted to ongoing_processes table because all current jobs are already in this table')


def select_ongoing_processes():
    """
    Select all data from ongoing_processes
    :return: - empty list if there are no ongoing_processes in db
             - list with chat_ids for ongoing_processes
    """

    SELECT_ONGOING_PROCESSES_QUERY = """SELECT * FROM ongoing_processes"""
    ongoing_processes = _run_query(SELECT_ONGOING_PROCESSES_QUERY)

    # need to take first element because result of query comes
    # in such format: [(12345,),(44459,),....(88890,)]
    # works only for not empty list
    ongoing_processes = [x[0] for x in ongoing_processes] if len(ongoing_processes) > 0 else ongoing_processes
    return ongoing_processes


def delete_ongoing_process(chat_id):
    """Delete row for chat_id in ongoing_processes table"""

    DELETE_PROCESS_QUERY = """DELETE FROM ongoing_processes
                            WHERE chat_id = (%s)"""
    _run_query(DELETE_PROCESS_QUERY, chat_id)
    logger.info(f'{chat_id} was deleted from ongoing_processes table')


def _run_query(query, *args):
    """
    General query runner
    :param query: query to execute
    :return: tuple with species and task if was inputed select query and
            it found data; otherwise returns None
    """

    # for manual input of credentials
    if MANUAL:
        connection = psycopg2.connect(host=HOST, database=DATABASE, user=USER, password=PASSWORD)

    # for heroku db
    else:
        DB_URL = os.environ['DATABASE_URL']
        connection = psycopg2.connect(DB_URL, sslmode='require')
    cursor = connection.cursor()
    cursor.execute(query, args)

    # check if query returns something
    # if no func will return None
    if cursor.description is None:
        data = None

    # if yes - set data to variable
    else:
        data = cursor.fetchall()

    cursor.close()
    connection.commit()
    connection.close()
    return data
