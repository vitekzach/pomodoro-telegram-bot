import pickle
import sys

import requests
import time
import logging
import signal


class TelegramBot:
    def __init__(self, token, polling_f=2, poll_sleep=0.1, pom_status_checking=1):
        """
        Initializing TelegramBot class
        Parameters
        ----------
        token: str
            your own bot's API token
        polling_f: float or int
            how many times per second polling happens
            should be high enough that one poll takes less than frequency
            influences has fast your bot will respond to queries
        """

        self.logging_setup()
        # logging.debug("Init started")
        self.token = token
        self.polling_f = polling_f
        self.loop_diff = polling_f**(-1)
        self.poll_sleep = poll_sleep
        self.user_infos = self.open_pickle('all_users.pkl')
        self.user_records = None  # TODO
        self.leaderboard = None  # TODO
        self.default_setting_dict = self.open_pickle('default_setting_dict.pkl')
        self.active_poms = None  # TODO
        self.last_responded_to = self.open_pickle('last_responded_to')
        self.pom_status_checking = pom_status_checking
        self.users_with_active_poms = []

        # register the original sigint so we can refer back to it later in code
        self.original_sigint = signal.getsignal(signal.SIGINT)
        # make our own SIGINT handler
        signal.signal(signal.SIGINT, self.exit_gracefully)

        logging.info("Instance initialized",
                     type="init")

    def send_message(self, chat_id, text, **kwargs):
        """
        Function that sends message to user
        Parameters
        ----------
        chat_id: int
            id of a user to send message to
        text: str
            test of message to send
        kwargs
            any other parameters Telegram SendMessage API accepts
            can be found here https://core.telegram.org/bots/api#sendmessage
        Returns
        -------

        """
        req_json = {"chat_id": chat_id,
                    "text": text,
                    }

        for key, val in kwargs.items():
            print(f"Adding {key} with val {val}")
            req_json[key] = val

        r = requests.post(url=f"https://api.telegram.org/bot{self.token}/sendMessage",
                          headers={"Content-Type": "application/json"},
                          json=req_json)
        if r.status_code == 200:
            logging.debug(f"Message sent to user '{self.user_infos[chat_id]['name']}' with content '{text}'",
                          kwargs=kwargs,
                          text=text,
                          type='message')
        else:
            logging.error(f"Message to '{chat_id}' with content '{text}' could not be sent!",
                          resp_json=r.json(),
                          resp_status=r.status_code,
                          text=text,
                          type='message')

        return r

    def get_update(self, **kwargs):
        # TODO implement offset
        req_json = {"offset": self.last_responded_to+1}

        for key, val in kwargs.items():
            print(f"Adding {key} with val {val}")
            req_json[key] = val

        # t0 = time.time()
        r = requests.post(url=f'https://api.telegram.org/bot{self.token}/getUpdates',
                          headers={"Content-Type": "application/json"},
                          json=req_json)
        # logging.debug(f"getUpdates took {time.time() - t0}s",
        #               type='update')

        if r.status_code != 200:
            logging.error("Update unsuccessful",
                          resp_json=r.json(),
                          resp_status=r.status_code,
                          type='update')

        return r.json()

    def start_bot(self):
        try:
            logging.info("Polling started!",
                         type='polling')
            time_last = time.time()
            last_pomstat_check = 9999

            while True:
                if time.time() - last_pomstat_check >= self.pom_status_checking and self.users_with_active_poms:
                    # logging.debug("Updating ongoing pomos",
                    #               type="pomo")
                    last_pomstat_check = time.time()
                    self.update_pomos()
                    # logging.debug("User updates finished",
                    #               type="pomo")

                if time.time() - time_last >= self.loop_diff:
                    # logging.debug("Pulling update...",
                    #               type="update")
                    r = self.get_update()
                    time_last = time.time()
                    self.parse_incoming_messages(r)

                    # logging.debug("GetUpdate finished",
                    #               type="update")

                else:
                    time.sleep(self.poll_sleep)
        except Exception:
            self.save_everything()
            logging.error("Exception occurred!",
                          exc_info=True,
                          type="update")


    def exit_gracefully(self, signum, frame):

        logging.info("SIGINT, saving data...",
                     type="shutdown")
        self.save_everything()
        logging.info("Saved! Exiting",
                     type="shutdown")
        sys.exit(0)

        # copied from here: https://stackoverflow.com/a/18115530
        # restore the original signal handler as otherwise evil things will happen
        # in raw_input when CTRL+C is pressed, and our signal handler is not re-entrant
        # signal.signal(signal.SIGINT, self.original_sigint)
        #
        # try:
        #     if input("Really quit? (y/n): ").lower().startswith('y'):
        #         self.save_everything()
        #         logging.info("Quitting by user prompt")
        #         sys.exit(1)
        #
        # except Exception as e:
        #     print("Ok ok, quitting")
        #     self.save_everything()
        #     logging.error("Quitting by other exception",
        #                  exc_info=1, stack_info=1)
        #     sys.exit(1)
        #
        # # restore the exit gracefully handler here
        # signal.signal(signal.SIGINT, self.exit_gracefully)

    def update_pomos(self):
        for user_id in self.users_with_active_poms:
            self.user_infos[user_id]['poms']['last_pom']['elapsed'] = \
                time.time() - self.user_infos[user_id]['poms']['last_pom']['last_status_change']
            logging.debug(
                f"{self.user_infos[user_id]['name']}: Ongoing for {self.user_infos[user_id]['poms']['last_pom']['elapsed']:2.0f}s",
                type="pomo")
            if self.user_infos[user_id]['poms']['last_pom']['elapsed'] >= self.user_infos[user_id]['settings'][
                'pom_length']:
                self.user_infos[user_id]['poms']['all_poms'] += 1
                self.user_infos[user_id]['poms']['foctime'] += self.user_infos[user_id]['settings']['pom_length']
                self.user_infos[user_id]['poms']['last_pom']['status'] = 'done'
                self.user_infos[user_id]['poms']['last_pom']['num'] += 1
                self.user_infos[user_id]['poms']['last_pom']['elapsed'] = 0
                self.users_with_active_poms.remove(user_id)
                self.send_message(chat_id=user_id, text="🍅 Congrats! You have finished your pomo! 🍅")
                logging.debug(f"Finished pomo from {self.user_infos[user_id]['name']}",
                              user_info_pom=self.user_infos[user_id]['poms'],
                              type="pomo")

    def parse_incoming_messages(self, response):
        for rec in response['result']:
            if rec['message']['from']['id'] not in self.user_infos:
                self.user_infos[rec['message']['from']['id']] = self.default_setting_dict.copy()
                self.user_infos[rec['message']['from']['id']]['name'] = rec['message']['from']['first_name']
                self.send_message(chat_id=rec['message']['from']['id'],
                                  text=f"Hey {rec['message']['from']['first_name']}! It seems like you're "
                                       f"new here, let me initialize some settings for you.")

            if 'text' in rec['message']:
                if "entities" in rec['message']:
                    for entity in rec["message"]["entities"]:
                        if entity["type"] == "bot_command":
                            command_name = rec['message']['text'][
                                           entity['offset'] + 1:entity['offset'] + entity['length']]
                            logging.debug(f"Found command '{command_name}'")

                            command = getattr(self, f"command_{command_name}", False)
                            if command:
                                command(record=rec)
                            else:
                                self.send_message(chat_id=rec['message']['from']['id'],
                                                  text=f"It looks like I don't know {command_name}! Please find all "
                                                       f"available commands at /commands.")

                else:
                    logging.debug(f"Received message '{rec['message']['text']}' from "
                                  f"'{rec['message']['from']['first_name']}'",
                                  text=rec['message']['text'],
                                  message=rec,
                                  type="message")
                    self.send_message(chat_id=rec['message']['from']['id'],
                                      text=rec['message']['text'])
            else:
                logging.warning(f"Received non text message.",
                                text=rec['message'],
                                type="message")
                nontext = "I see you sent me a non text message. I'm sorry, but I don't know how to deal with those yet."
                self.send_message(chat_id=rec['message']['from']['id'],
                                  text=nontext)

            self.last_responded_to = rec['update_id']
        # TODO only text, no pictures!
        # TODO what about sticker?

    def command_startpom(self, record):
        self.send_message(chat_id=record['message']['from']['id'],
                          text="Your pomodoro has been started!")
        logging.debug(f"Adding '{record['message']['from']['first_name']}' to pom users list",
                      type="pomo")
        self.users_with_active_poms.append(record['message']['from']['id'])
        self.user_infos[record['message']['from']['id']]['poms']['last_pom'][
            'last_status_change'] = time.time()

    def command_reset_stats(self, record):
        from_id = record['message']['from']['id']
        self.user_infos[from_id]['poms']['all_poms'] = 0
        self.user_infos[from_id]['poms']['foctime'] = 0
        self.send_message(chat_id=from_id,
                          text='Your stats have been reset!')

    def command_stats(self, record):
        from_id = record['message']['from']['id']
        from_poms = self.user_infos[record['message']['from']['id']]['poms']
        self.send_message(chat_id=from_id,
                          text=f"Completed poms: {from_poms['all_poms']} \nFocused time: {from_poms['foctime']}")
                          # text=f"{self.user_infos}")

    def command_status(self, record):
        from_id = record['message']['from']['id']
        if from_id in self.users_with_active_poms:
            elapsed = self.user_infos[record['message']['from']['id']]['poms']['last_pom']['elapsed']
            self.send_message(chat_id=from_id,
                              text=f"Current pomodoro status: {elapsed//60:.0f}:{elapsed%60:02.0f}")
        else:
            self.send_message(chat_id=from_id,
                              text="It looks like you don't have any active pomodoros or breaks!")

    def save_everything(self):
        self.save_pickle('last_responded_to', self.last_responded_to)
        self.save_pickle('all_users.pkl', self.user_infos)

    @staticmethod
    def logging_setup():
        """
        # TODO
        Returns
        -------

        """
        import seqlog

        seqlog.configure_from_file("seq_dev.yml")

    @staticmethod
    def save_pickle(filename, obj):
        with open(filename, 'wb') as file:
            pickle.dump(obj, file)

    @staticmethod
    def open_pickle(filename):
        with open(filename, 'rb') as file:
            loaded_file = pickle.load(file)

        return loaded_file

    # TODO users and settings
    # TODO leaderboard
    # TODO recognize commands
    # TODO polling parameter
    # TODO keyboard
    # TODO logging
    # TODO catch incoming ctrl c event and save everything
    # TODO multi threaded
    # TODO init bot
    # TODO decorator for commands
    # TODO get pomo status
    # TODO auto start break?
    # TODO async, threading?
