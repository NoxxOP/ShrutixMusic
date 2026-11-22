
from pyrogram import Client
import config
from ..logging import LOGGER

assistants = []
assistantids = []

class Userbot(Client):
    def __init__(self):
        self.one = Client(
            name="ShrutiXAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
            no_updates=True,
        )
        self.two = Client(
            name="ShrutiXAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
            no_updates=True,
        )
        self.three = Client(
            name="ShrutiXAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
            no_updates=True,
        )
        self.four = Client(
            name="ShrutiXAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
            no_updates=True,
        )
        self.five = Client(
            name="ShrutiXAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
            no_updates=True,
        )

    async def start(self):
        LOGGER(__name__).info(f"Starting Assistants...")
        
        if config.STRING1:
            try:
                await self.one.start()
                LOGGER(__name__).info("Assistant 1 started successfully")
                
                                          
                self.one.id = self.one.me.id
                self.one.name = self.one.me.mention
                self.one.username = self.one.me.username
                LOGGER(__name__).info(f"Assistant 1 ID: {self.one.id}, Username: {self.one.username}")
                
                                           
                try:
                    await self.one.join_chat("ShrutiBots")
                    await self.one.join_chat("ShrutiSupportChat")
                    LOGGER(__name__).info("Assistant 1 joined support chats")
                except Exception as e:
                    LOGGER(__name__).warning(f"Assistant 1 failed to join support chats: {e}")
                
                                             
                if not config.LOGGER_ID:
                    LOGGER(__name__).error("LOGGER_ID is not set in config!")
                    exit()
                
                LOGGER(__name__).info(f"Trying to send message to LOGGER_ID: {config.LOGGER_ID}")
                
                                                                                
                try:
                                                         
                    chat_info = await self.one.get_chat(config.LOGGER_ID)
                    LOGGER(__name__).info(f"Logger group info: {chat_info.title}")
                    
                                                               
                    member = await self.one.get_chat_member(config.LOGGER_ID, self.one.id)
                    LOGGER(__name__).info(f"Assistant 1 status in logger group: {member.status}")
                    
                                         
                    await self.one.send_message(config.LOGGER_ID, "✅ Assistant 1 Started Successfully")
                    LOGGER(__name__).info("Assistant 1 successfully sent message to logger group")
                    
                except Exception as e:
                    LOGGER(__name__).error(f"Assistant 1 failed to access logger group. Error: {type(e).__name__}: {e}")
                    LOGGER(__name__).error(
                        "Make sure:\n"
                        "1. LOGGER_ID is correct\n"
                        "2. Assistant account is added to the log group\n"
                        "3. Assistant is promoted as admin in log group\n"
                        "4. Group privacy settings allow bots to send messages"
                    )
                    exit()
                
                assistants.append(1)
                assistantids.append(self.one.id)
                LOGGER(__name__).info(f"Assistant 1 Started as {self.one.name}")
                
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 1: {type(e).__name__}: {e}")
                exit()

        if config.STRING2:
            try:
                await self.two.start()
                
                try:
                    await self.two.join_chat("ShrutiBots")
                    await self.two.join_chat("ShrutiSupportChat")
                except:
                    pass
                    
                assistants.append(2)
                
                try:
                    await self.two.send_message(config.LOGGER_ID, "✅ Assistant 2 Started")
                except Exception as e:
                    LOGGER(__name__).error(f"Assistant 2 failed to access logger group: {e}")
                    exit()
                    
                self.two.id = self.two.me.id
                self.two.name = self.two.me.mention
                self.two.username = self.two.me.username
                assistantids.append(self.two.id)
                LOGGER(__name__).info(f"Assistant 2 Started as {self.two.name}")
                
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 2: {e}")

                                                 
        if config.STRING3:
            try:
                await self.three.start()
                
                try:
                    await self.three.join_chat("ShrutiBots")
                    await self.three.join_chat("ShrutiSupportChat")
                except:
                    pass
                    
                assistants.append(3)
                
                try:
                    await self.three.send_message(config.LOGGER_ID, "✅ Assistant 3 Started")
                except Exception as e:
                    LOGGER(__name__).error(f"Assistant 3 failed to access logger group: {e}")
                    exit()
                    
                self.three.id = self.three.me.id
                self.three.name = self.three.me.mention
                self.three.username = self.three.me.username
                assistantids.append(self.three.id)
                LOGGER(__name__).info(f"Assistant 3 Started as {self.three.name}")
                
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 3: {e}")

        if config.STRING4:
            try:
                await self.four.start()
                
                try:
                    await self.four.join_chat("ShrutiBots")
                    await self.four.join_chat("ShrutiSupportChat")
                except:
                    pass
                    
                assistants.append(4)
                
                try:
                    await self.four.send_message(config.LOGGER_ID, "✅ Assistant 4 Started")
                except Exception as e:
                    LOGGER(__name__).error(f"Assistant 4 failed to access logger group: {e}")
                    exit()
                    
                self.four.id = self.four.me.id
                self.four.name = self.four.me.mention
                self.four.username = self.four.me.username
                assistantids.append(self.four.id)
                LOGGER(__name__).info(f"Assistant 4 Started as {self.four.name}")
                
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 4: {e}")

        if config.STRING5:
            try:
                await self.five.start()
                
                try:
                    await self.five.join_chat("ShrutiBots")
                    await self.five.join_chat("ShrutiSupportChat")
                except:
                    pass
                    
                assistants.append(5)
                
                try:
                    await self.five.send_message(config.LOGGER_ID, "✅ Assistant 5 Started")
                except Exception as e:
                    LOGGER(__name__).error(f"Assistant 5 failed to access logger group: {e}")
                    exit()
                    
                self.five.id = self.five.me.id
                self.five.name = self.five.me.mention
                self.five.username = self.five.me.username
                assistantids.append(self.five.id)
                LOGGER(__name__).info(f"Assistant 5 Started as {self.five.name}")
                
            except Exception as e:
                LOGGER(__name__).error(f"Failed to start Assistant 5: {e}")

    async def stop(self):
        LOGGER(__name__).info(f"Stopping Assistants...")
        try:
            if config.STRING1:
                await self.one.stop()
            if config.STRING2:
                await self.two.stop()
            if config.STRING3:
                await self.three.stop()
            if config.STRING4:
                await self.four.stop()
            if config.STRING5:
                await self.five.stop()
        except:
            pass
