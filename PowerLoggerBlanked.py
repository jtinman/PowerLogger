# -*- coding: utf-8 -*-

# TODO Incorporate text or email alerts
# Text Message sending managed by textlocal.com

import datetime
import pytz
import time
import random
import csv
import dropbox
import os.path
import schedule
from influxdb import InfluxDBClient
# import textLocal

############################################################################

"""
CUSTOM VALUES FOR EACH INSTALLATION
Change these according to supply details
"""
# Start and end times for peak charge rates
peakTimeStart = datetime.time(8, 0, 0)
peakTimeEnd = datetime.time(23, 0, 0)

# Costs of electricity in £/kWh
costPeak = 0.128636
costOffPeak = 0.89862

# Time interval of sampling in seconds
period = 5

# Details of logging device
site = "********"
dlogger = "********"
capacity = 400      # Max amperage on each phase

# Local directory for saving CSV Files
directory = "********"

# Dropbox details
access_token = '********'
# Dropbox folder to save log files in
dbxpath = "/Power Logger Readings/" + str(site) + "/" + str(dlogger) + "/"

# InfluxDB variables
IP = '***.***.***.***'
DB = '********'
User = '********'
Password = '********'
client = InfluxDBClient(host=IP, port=8086, username=User, password=Password, database=DB)

############################################################################
# Helper functions
############################################################################
def timeCode(tic):
    """Function for timing an operation
    Define a start time 'start' outside the function with time.perf_counter()
    Then after the operation call timeCode(start) to give the operating time"""
    toc = time.perf_counter()
    diff = ('Time:{:.3f}'.format(toc-tic))
    print(diff)
    return toc

def generate_random_readings(currents, capacity):
    """ Placeholder function for live readings. Simulates a fluctuating
    wandering current to use for unit testing"""
    output = []
    for I in currents:
        if I < 10:
            I = I + (random.randint(0,10))
        elif I > (1.1 * capacity):
            I = I - (random.randint(-10,0))
        else:
            I = I + (random.randint(-10,10))
        output.append(I)
    return output
    
def time_in_range(start, end, x):
    """Function to check if a given time is within a defined range
    Return True if x is in the range [start, end]"""
    if start <= end:
        return start <= x <= end
    else:
        return start <= x or x <= end

def write_to_DB(input):
    """Function for sending JSON packaged data to InfluxDB"""
    json_body = [{"measurement": "sensorData", "Timestamp": now, "fields":{"I1": input.I[0], "I2": input.I[1], "I3": input.I[2]}}]
    
    client.switch_database('********')
    client.write_points(json_body)
############################################################################

class logger(object):
    """Class to take readings from the sensors, store values, and process into format for writing to CSV file"""

    def __init__(self, now):
        self.time = None
        self.date = None
        self.I = [0]*3
        self.V = [0.0]*3
        self.P = [0.0]*3
        self.CCost = 0.0
        self.I1_flag = 0
        self.I2_flag = 0
        self.I3_flag = 0
        
    def flagReset(self, I):
        """
        This needs to be developed, but is the part of an Overcurrent alarm
        """
        if I == 1:    
            self.I1_flag = 0
        if I == 2:
            self.I2_flag = 0
        if I == 3:
            self.I3_flag = 0
    
    def getreadings(self):
        """
        output list of values for writing to CSV file:
        [0]: Timestamp %H:%M:%S - Hours, Minutes, Seconds (All 0-padded)
        [1]: Datestamp %a %d %b %Y - 3-letter Day, Day digit, Month digit, Year 2-digit
        [2]: I1 (int) from sensor, initally 0
        [3]: I2 (int) from sensor, initally 0
        [4]: I3 (int) from sensor, initally 0
        [5]: V1 (float) from sensor, initally 0.0
        [6]: V2 (float) from sensor, initally 0.0
        [7]: V3 (float) from sensor, initally 0.0
        [8]: P1 (float) from I1*V1, initally 0.0
        [9]: P2 (float) from I2*V2, initally 0.0
        [10]: P3 (float) from I3*V3, initally 0.0
        [11]: Total cumulative cost (float), initially 0.0
        """
        data = [self.time, self.date] + self.I + self.V + self.P + [self.CCost]
        return data
    
    def print_data(self):
        print("-"*80)
        print(self.time, self.date)
        print('I1:{:>10.2f}  I2:{:>10.2f}  I3:{:>10.2f}'.format(self.I[0],self.I[1],self.I[2]))
        print('V1:{:>10.2f}  V2:{:>10.2f}  V3:{:>10.2f}'.format(self.V[0],self.V[1],self.V[2]))
        print("-"*80)
    
    def updatereadings(self, now):
        # Read data from sensors and update values
        # TODO Change from randomising figures to reading sensor values
        self.I = generate_random_readings(self.I, capacity)
        
        # TODO: Come up with better alarm system
        # Check if any phases are overloaded, add to flag if so
        if self.I[0] > capacity:
             self.I1_flag += 1
        if self.I[1] > capacity:
             self.I2_flag += 1
        if self.I[2] > capacity:
             self.I3_flag += 1
        
        # Update time and date stamps
        self.time = datetime.datetime.now().strftime('%H:%M:%S')
        self.date = datetime.datetime.now().strftime('%a %d %b %Y')
        
        # Calculate power draw based on Voltage and Current readings
        # Update power values
        self.P = [I * V for I, V in zip(self.I, self.V)]
                
        # Calculate kWh for period
        kWh = sum(self.P) * (period/(60*60))
        
        # Calculate cost based on time and add to readings list
        if time_in_range(peakTimeStart, peakTimeEnd, now.time()):
            cost = costPeak
        else:
            cost = costOffPeak
        self.CCost = self.CCost + (cost * kWh)
      
        
class CSVFile(object):
    """
    Class for writing readings to a CSV file
    """
    def __init__(self):
        headers = ["Time", "Date", "I1", "I2", "I3", "V1", "V2", "V3", "P1", "P2", "P3", "Cumulative P Total", "Cumulative Cost"]
        
        # Check if a file already exists or not before writing headers
        if not os.path.isfile(self._path):
             with open(self._path, 'a') as file:
                writer = csv.writer(file, dialect='excel')
                writer.writerow([logger])
                writer.writerow(headers)
    
    def get_path(self):
        return self._path
    
    def get_name(self):
        return self._name
    
    def write_line(self, data):
        self.data = data

        with open(self._path, 'a') as file:
            writer = csv.writer(file, dialect='excel')
            writer.writerow(data)
    
    def read_last_time(self):
        """
        Function for reading back the last line of a saved CSV file
        """
        try:
            with open(self._path, 'r') as f:
                timestr = list(reversed(list(csv.reader(f))))[0][0] +'.000000'
                lastTime = datetime.datetime.strptime(timestr, '%H:%M:%S.%f')
                return lastTime
        except:
            now_str = str(datetime.datetime.now().time())
            t_now = datetime.datetime.strptime(now_str, '%H:%M:%S.%f')
            return t_now
    
    def check_for_blanks(self):
        """
        Function to check to see if file is up to date, or if time has
        elapsed since the last recorded value
        """
        # Create a definition of now
        now_str = str(datetime.datetime.now().time())
        t_now = datetime.datetime.strptime(now_str, '%H:%M:%S.%f')

        # Check if there has been a gap in readings
        gap = t_now - self.read_last_time()
        
        # Write blanked out lines for each missed reading period
        gap_secs = gap.total_seconds()
        if gap_secs > (2 * period):
            print('Gap in s: ' + str(gap_secs))
            # while gap_secs > 0:
            #     dayFile.write_line(['X']*12)
            #     gap_secs -= period
            
    def backup(self):
        # Check if file already exists, if so add time to filename
        uploadPath = dbxpath + self.get_name()
        try:
            dbx.files_get_metadata(uploadPath)
            flag = True
        except:
            flag = False
        print(flag)
        print(uploadPath)
        if flag == True:
            uploadPath += now.strftime('%H:%M:%S')
        print(uploadPath)
        with open(self.get_path(), 'rb') as f:
            dbx.files_upload(f.read(), uploadPath)
        

class CSVFileDay(CSVFile):
    """
    Class inheriting from CSVFile that records the readings of the current day
    """
    def __init__(self, dlogger, now, directory, day):
        """.csv file of logger readings for 1 day
        Args:   dlogger (logger): the logger being recorded
                now (datetime): time being recorded
                directory (string): file path where fill is saved
                day (int): day date that this file references"""
        self.logger = dlogger 
        self._name = str(self.logger) + " Daily Powerlog " + now.strftime('%d-%m-%y; %a %d %b') + ".csv"
        self._path = directory + self._name
        self.day = day
        self.tsflag = 0
       
class CSVFileMonth(CSVFile):
    """
    Class inheriting from CSVFile that records the readings of a whole month
    """
    def __init__(self, dlogger, now, directory, month):
        self.logger = dlogger
        self._name = str(self.logger) + " Monthly Powerlog " + now.strftime('%m-%y %b') + ".csv"
        self._path = directory + self._name
        self.month = month
            

############################################################################
def update(dayFile, monthFile):
    """
   Function that runs all the code every 'period' (5 seconds) to take readings, do calculations, and record values
    """
    # Update 'now'
    now = datetime.datetime.now(pytz.timezone('Europe/London'))
    print(now)
    
    # Check if there is a new day or month since the last reading
    # Create new files if so
    if now.month != monthFile.month:
        # Check if actually a new month, or restarting program
        if monthFile.month == None:
            monthFile.month = now.month
        else:
            monthFile.backup()
            monthFile = CSVFileMonth(dlogger, now, directory, now.month)
                    
    if now.minute != dayFile.day:
        # Check if actually a new day, or restarting program
        print('***********', dayFile.day)
        if dayFile.day == None:
            dayFile.day = now.day
        else:
            dayFile.backup()
            dayFile = CSVFileDay(dlogger, now, directory, now.day)
    
    # Append the logger data to the current files
    dayFile.write_line(power.getreadings())
    monthFile.write_line(power.getreadings())
    
    # Write line to Influx DB
    write_to_DB(power)
    print(power.I)
    
    # Read from Sources
    power.updatereadings(now)
    
    # TODO Get TextLocal working
    # If current running continuously hot, send alarm texts
    #if power.flag > 10:
    #    textLocal.sendText(message, numbers)
    #    power.flagreset()
        
    # Counter code to check how long program has run for
    global count
    count += 1
    print(count)

##############################################################################
# Start of Program
##############################################################################
# Set initial variables
now = datetime.datetime.now(pytz.timezone('Europe/London'))
power = logger(now)
dayFile = CSVFileDay(dlogger, now, directory, None)
monthFile = CSVFileMonth(dlogger, now, directory, None)
dbx =  dropbox.Dropbox(access_token)
count = 0

# Create timing schedule for logger readings every 5s
for i in range(11):
    schedule.every().minute.at(":" + str((i+1)*5).zfill(2)).do(update, dayFile, monthFile)

try:
    while(True):
        schedule.run_pending()
           
except KeyboardInterrupt:
    print("Press Ctrl-C to terminate while statement")
    pass
