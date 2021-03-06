import csv
import calendar
import datetime
import logging
import pytz
from dateutil import relativedelta

logging.getLogger(__name__)

def working_with_csv(servers_for_patching, db_cur, today, os, time_zone):
    '''Function for raise other function with csv-creation from auto_mm.py file'''
    servers_for_write_to_csv_mm, servers_for_write_to_csv_without_mm, servers_with_additional_monitors,\
    servers_for_write_to_csv_notify_before_4_days, error_list_from_csv = create_csv_list_with_servers_for_write_and_with_additional_monitors(servers_for_patching, db_cur, today, time_zone)
    if servers_for_write_to_csv_mm:
        write_to_csv('linux_MM_{date}_patching_{name}'.format(date=today.strftime("%b_%Y"), name=os), servers_for_write_to_csv_mm, 'long')
        print('Hey, csv-file linux_MM_{date}_patching_{name}.csv has been compiled!'.format(date=today.strftime("%b_%Y"), name=os))
        if servers_with_additional_monitors:
            write_to_csv('linux_MM_CIS_{date}_patching_{name}'.format(date=today.strftime("%b_%Y"), name=os),
                         set(servers_with_additional_monitors), "long")
            print("FYI: csv-file linux_MM_CIS_{date}_patching_{name}.csv created!".format(date=today.strftime("%b_%Y"), name=os))
    if servers_for_write_to_csv_notify_before_4_days:
        write_to_csv('linux_e_mail_notify_before_4_days_{date}_patching_{name}'.format(date=today.strftime("%b_%Y"), name=os), set(servers_for_write_to_csv_notify_before_4_days), 'short')
        print("FYI: csv-file linux_e_mail_notify_before_4_days_{date}_patching_{name}.csv created!".format(date=today.strftime("%b_%Y"), name=os))
    if servers_for_write_to_csv_without_mm:
        write_to_csv('linux_without_MM_{date}_patching_{name}'.format(date=today.strftime("%b_%Y"), name=os), servers_for_write_to_csv_without_mm, 'long')
        print('Hey, csv-file linux_without_MM_{date}_patching_{name}.csv has been compiled!'.format(date=today.strftime("%b_%Y"), name=os))
    return error_list_from_csv


def get_patching_start_date(today, window_code, db_cur):
    '''function for return patching start date (year, minth and day)'''
    #get calendar for current month
    cal=calendar.Calendar(firstweekday=0)
    cal_current_month=cal.monthdayscalendar(today.year, today.month)
    #get patching code from database
    patch_code_from_db=db_cur.execute("SELECT IDX, WEEKDAY FROM WINDOW_CODE WHERE CODE =:window_code COLLATE NOCASE", {'window_code' : window_code }).fetchone()
    if not patch_code_from_db:
        return None
    #get number of week where second Tuesday (index starts from 0)
    week_with_second_tuesday = 1
    if not cal_current_month[0][1]:
        week_with_second_tuesday = 2
    #get patching date time
    try:
        patch_date= datetime.date(year=today.year, month=today.month, day=cal_current_month[patch_code_from_db[0]+week_with_second_tuesday][patch_code_from_db[1]])
    #if patching date not in current month -- get next month and start date
    except (ValueError,IndexError):
        next_month_and_year = today + relativedelta.relativedelta(months=1)
        cal_next_month = cal.monthdayscalendar(next_month_and_year.year, next_month_and_year.month)
        patch_date = datetime.date(year=next_month_and_year.year, month=next_month_and_year.month, day=cal_next_month[patch_code_from_db[0]+
                                    week_with_second_tuesday-len(cal_current_month)+1][patch_code_from_db[1]])
    return patch_date


def write_to_csv(csv_name, list_for_write, csv_format):
    '''function for generate csv-files'''
    responsible_user='Ilyas Ganiev'
    action='schedule'
    comment='patching'
    with open(str(csv_name) + '.csv', 'w') as csv_mm:
        csv_mm_writer=csv.writer(csv_mm, delimiter=';')
        if csv_format=='long':
            csv_mm_writer.writerow(['action','start_downtime','end_downtime','comment','responsible_user','host','service'])
            for current_list_for_write in list_for_write:
                csv_mm_writer.writerow([action, current_list_for_write[1], current_list_for_write[2], comment, responsible_user, current_list_for_write[0], current_list_for_write[3]])
        else:
            for current_list_for_write in list_for_write:
                csv_mm_writer.writerow([current_list_for_write[0], current_list_for_write[1]])


def create_csv_list_with_servers_for_write_and_with_additional_monitors(servers_for_patching, db_cur, today, time_zone_from_settings):
    '''return list with mm plan'''
    servers_for_write_to_csv_with_mm=[]; servers_with_additional_monitors=[];
    error_list=[]; servers_before_4_days=[]; servers_without_mm = []
    for current_server in servers_for_patching:
        data_from_sqlite_db = db_cur.execute('SELECT WINDOW_CODE, NEED_MM, NEED_EMAIL_BEFORE_4_DAYS FROM SERVERS \
                                            WHERE SERVER_NAME=:current_server COLLATE NOCASE',
                                            {'current_server':current_server}).fetchone()
        if not data_from_sqlite_db:
            error_list.append('Server {server} does not exist on database...'.format(server=current_server))
            continue
        server_window_code, need_mm, need_email_before_four_days = data_from_sqlite_db
        if need_mm==0:
            print("For server {server} maintenance mode is not required")
        #get patching start day
        patching_start_date=get_patching_start_date(today, server_window_code, db_cur)
        server_name_from_db, time_zone, patching_start_time, patching_duration, additional_monitors=db_cur.execute('SELECT SERVER_NAME, TIMEZONE, START_TIME, DURATION_TIME, ADDITIONAL_MONITORS FROM SERVERS\
                                                               WHERE SERVER_NAME=:current_server COLLATE NOCASE',
                                                              {'current_server' : current_server}).fetchone()
        #get datetime for patching start
        patching_start_datetime = datetime.datetime(year=patching_start_date.year, month=patching_start_date.month, day=patching_start_date.day, hour=int(patching_start_time[0:2]), minute=int(patching_start_time[3:]))
        #set time zome for starting date
        patching_start_datetime=pytz.timezone(time_zone).localize(patching_start_datetime)
        #convert timezone from db to desired timezone
        patching_start_datetime=patching_start_datetime.astimezone(pytz.timezone(time_zone_from_settings))
        #get patching end time
        patching_end_datetime=patching_start_datetime+datetime.timedelta(hours=int(patching_duration[0:2]), minutes=int(patching_duration[3:]))
        if need_mm == 1:
            servers_for_write_to_csv_with_mm.append((server_name_from_db, patching_start_datetime.strftime('%d.%m.%Y %H:%M'), patching_end_datetime.strftime('%d.%m.%Y %H:%M'), ''))
            if additional_monitors == 1:
                additional_cis = db_cur.execute('SELECT ADDITIONAL_CIS, ADITIONAL_MONITOR_NAME FROM ADDITIONAL_MONITORS WHERE SERVER_NAME=:current_server COLLATE NOCASE', {'current_server': current_server}).fetchall()
                if not additional_cis:
                    error_list.append("Error: For server {server_name} should be additional monitors...".format(server_name=current_server))
                else:
                    for current_cis in additional_cis:
                        servers_with_additional_monitors.append((current_cis[0], patching_start_datetime.strftime('%d.%m.%Y %H:%M'), patching_end_datetime.strftime('%d.%m.%Y %H:%M'), current_cis[1]))
        elif need_mm == 0:
            servers_without_mm.append((server_name_from_db, patching_start_datetime.strftime('%d.%m.%Y %H:%M'), patching_end_datetime.strftime('%d.%m.%Y %H:%M'), ''))
        if need_email_before_four_days==1:
            servers_before_4_days.append((server_name_from_db, patching_start_datetime.strftime('%d.%m.%Y %H:%M')))
    return servers_for_write_to_csv_with_mm, servers_without_mm, servers_with_additional_monitors, servers_before_4_days, error_list
