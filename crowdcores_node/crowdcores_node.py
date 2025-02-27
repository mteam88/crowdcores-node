import asyncio
import websockets
import time
import json
import torch
from transformers import pipeline
import sys
import os

#polyfills for earlier  versions of python
try:
    asyncio.create_task
except AttributeError:
    def asyncio_create_task(coro, *, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        return loop.create_task(coro)
else:
    asyncio_create_task = asyncio.create_task

try:
    asyncio.run
except AttributeError:
    def asyncio_run(coroutine, debug=False):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coroutine)
        finally:
            loop.close()
else:
    asyncio_run = asyncio.run




model_names=[];
models_pipelines={};

async def run_async(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, func, *args, **kwargs)
    return result

def do_process_pipeline_request(websocket,message):
    print("processing");
    try:

        if torch.cuda.is_available():
            device_id=0;
        else:
            device_id=-1;

        request_data = message['pipeline_data']
        args=request_data["args"];
        kwargs=request_data["kwargs"];
        init_args=request_data["init_args"];
        init_kwargs=request_data["init_kwargs"];
        task=init_args[0];
        model_name=init_kwargs['model']
        #model_pipeline = pipeline(*init_args,**init_kwargs)
        print("Processing pipeline request:",task,"-",model_name)
        model_pipeline = pipeline(task,model=model_name,device=device_id)

        r=model_pipeline(*args,**kwargs)
        response={
            "success":1,
            "pipeline_response_result":r
        }
        print("Completed pipeline request:",task,"-",model_name)
        return response;
    except Exception as e:
        response={
            "success":0,
            "exception_name":e.__class__.__name__,
            "exception_message":str(e)
        }
        return response


async def process_pipeline_request(websocket,message):
    response = await run_async(do_process_pipeline_request,websocket,message)
    data = {'command': 'completed_pipeline_request','pipeline_response':response,'pipeline_request':message}
    await websocket.send(json.dumps(data))


async def init_load_models(websocket):
    await run_async(load_models,websocket)
    print("Models Download Complete")
    data = {'command': 'completed_models_download'}
    await websocket.send(json.dumps(data))

def load_models(websocket):
    for model_name, model_data in model_names.items():
        print("Loading Model:",model_name);
        try:
            pipeline(model=model_name,task=model_data['pipeline_tag'])
        except Exception as e:
            print(repr(e))
            print('Model could not load, skipping download...')


async def receive_loop(websocket):
    while True:
        message = await websocket.recv()
        message_json = json.loads(message)

        if message_json['command'] == 'ping':
            data = {'command': 'pong'}
            await websocket.send(json.dumps(data))

        if message_json['command'] == 'got_models_names_list':
            global model_names
            model_names=message_json['model_names_list']
            asyncio_create_task(init_load_models(websocket))

        if message_json['command'] == 'process_pipeline_request':
            asyncio_create_task(process_pipeline_request(websocket,message_json))


async def send_loop(websocket):
    while True:
        #print("sending");
        await asyncio.sleep(15)
        data = {'command': 'ping'}
        await websocket.send(json.dumps(data))

async def start_node(websocket):
        data = {'command': 'node_started'}
        API_KEY = os.getenv('CROWDCORES_API_KEY');
        if API_KEY:
            data['api_key']=API_KEY;
        await websocket.send(json.dumps(data))

async def client():
    while True:
        try:
            async with websockets.connect("ws://ws.crowdcores.com") as websocket:
                consumer_task=asyncio_create_task(receive_loop(websocket))
                producer_task=asyncio_create_task(send_loop(websocket))
                asyncio_create_task(start_node(websocket))
                done, pending = await asyncio.wait(
                    [consumer_task,producer_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                #await asyncio.Future()
        #except (OSError, websockets.exceptions.ConnectionClosed) as e:
        except Exception as e:
            print(f"Connection failed: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)



def main():
    asyncio_run(client())

if __name__ == "__main__":
    main()

