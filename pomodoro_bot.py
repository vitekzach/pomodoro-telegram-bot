import pickle
import sys

import requests
import time
import logging
import signal


class TelegramBot:
    def __init__(self, token, polling_f=2, poll_sleep=0.1):
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
        logging.debug("Init started")
        self.token = token
        self.polling_f = polling_f
        self.loop_diff = polling_f**(-1)
        self.poll_sleep = poll_sleep
        self.user_settings = None  # TODO
        self.user_records = None  # TODO
        self.leaderboard = None  # TODO
        self.default_setting_dict = None  # TODO
        self.active_poms = None  # TODO
        self.last_responded_to = self.open_pickle('last_responded_to')  # TODO

        # register the original sigint so we can refer back to it later in code
        self.original_sigint = signal.getsignal(signal.SIGINT)
        # make our own SIGINT handler
        signal.signal(signal.SIGINT, self.exit_gracefully)

        logging.info("Instance initialized")

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
            logging.debug(f"Message sent to user {chat_id} with content {text}",
                          kwargs=kwargs,
                          text=text)
        else:
            logging.error(f"Message to {chat_id} with content {text} could not be sent!",
                          resp_json=r.json(),
                          resp_status=r.status_code,
                          text=text)

        return r

    def get_update(self, **kwargs):
        # TODO implement offset
        req_json = {"offset": self.last_responded_to+1}

        for key, val in kwargs.items():
            print(f"Adding {key} with val {val}")
            req_json[key] = val

        r = requests.post(url=f'https://api.telegram.org/bot{self.token}/getUpdates',
                          headers={"Content-Type": "application/json"},
                          json=req_json)

        if r.status_code != 200:
            logging.error("Update unsuccessful",
                          resp_json=r.json(),
                          resp_status=r.status_code)

        return r.json()




    def start_bot(self):
        try:
            logging.info("Polling started!")
            time_last = time.time()
            while True:
                if time.time() - time_last >= self.loop_diff:
                    time_last = time.time()

                    r = self.get_update()

                    for rec in r['result']:
                        if 'text' in rec['message']:
                            logging.debug(f"Received message {rec['message']['text']}",
                                          text=rec['message']['text'])
                            self.send_message(chat_id=rec['message']['from']['id'],
                                              text=rec['message']['text'])
                        else:
                            logging.warning(f"Received non text message.",
                                            text=rec['message'])
                            nontext = "I see you sent me a non text message. I'm sorry, but I don't know how to deal with those yet."
                            self.send_message(chat_id=rec['message']['from']['id'],
                                              text=nontext)

                        self.last_responded_to = rec['update_id']
                else:
                    time.sleep(self.poll_sleep)
        except Exception:
            logging.error("Error occurred!",
                          exc_info=True, stack_info=True)




    def exit_gracefully(self, signum, frame):

        logging.info("SIGINT, saving data...")
        self.save_everything()
        logging.info("Saved! Exiting")
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

    def parse_incoming_message(self):
        pass
        # TODO only text, no pictures!
        # TODO what about sticker?

    def save_everything(self):
        self.save_pickle('last_responded_to', self.last_responded_to)

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
