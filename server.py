from flask import Flask, request, render_template
import json, os
import dotenv
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

app = Flask('app')

DATAPATH = "./data"

from dotenv import load_dotenv
load_dotenv(".env")


# Make Containter 
connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
blob_service_client = BlobServiceClient.from_connection_string(connect_str)

# Create a unique name for the container
container_name = "rsvp-blob"

try:
    # Create the container
    container_client = blob_service_client.create_container(container_name)
except ResourceExistsError:
    container_client = blob_service_client.get_container_client(container_name)
  

@app.route("/")
def form():
    return render_template("form.html")


@app.route("/view")
def view_invite():
    # to = "Sarah"
    # event = "Artemis' birthday party"
    # date = "February 10th"
    # time = "4am"
    # sender = "Jack"

    to = request.args.get("to")
    event = request.args.get("event")
    date = request.args.get("date")
    time = request.args.get("time")
    sender = request.args.get("sender")
    style = request.args.get('style')
    eventId = sender + "|" + event


    # http://192.168.1.122:8080/view?style=kids
    # http://192.168.1.122:8080/view?event=Bibi's+Bday&to=Clair&date=Monday+32nd+of+Mocktober&time=4pm&sender=Renee&style=cat
    

    template = "invite-" + style + ".html"
    

    return render_template(template, to=to, event_name=event, date=date, time=time, sender=sender, eventId=eventId)

@app.route("/events")
def list_events():
    blob_list = container_client.list_blobs()
    events = []
    for event_file in blob_list:
        file_name = event_file.name
        event_ID = file_name
        
        name, event_name = event_ID.split("|")
        events.append((file_name, name, event_name))
    return render_template("events.html", event_list=events)
    
    
@app.route("/event-rsvps/<event_file>")
def event_rsvps(event_file):
    event_ID = event_file[0:-4]
    name, event_name = event_ID.split("|")
    # return event_ID
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=event_file)
    attendees = str(blob_client.download_blob().readall(), "utf-8")
    attendees = attendees.split("\n")
    
    return render_template("rsvp_list.html", attendee_list=attendees, event_name=event_name, name=name)




@app.route("/rsvp", methods=('GET', 'POST'))
def rsvp():
    data = request.json
    event_data = data["ID"].split(",")
    attendee = event_data[0]
    event_ID = event_data[1]
    
    # filename = event_ID + ".txt"
    # filepath = os.path.join(local_path, filename)
    # with open(filepath ,"w") as f:
    #     f.write(attendee)

    try:
        sync_blob(event_ID, attendee)
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
    except:
        return json.dumps({'success':True}), 400, {'ContentType':'application/json'}


def sync_blob(event_ID, attendee):
    """
    If a blob for the event exists download it, and add the new RSVP (if it's not already in the list)
    If a blob doesn't exist create one with the RSVP
    If something goes wrong return False
    """
    filename = event_ID + ".txt"

    local_file = os.path.join(DATAPATH, filename)
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=filename)

    # Try and get an exisitng blob
    try:
        print("\nDownloading blob to \n\t" + local_file)

        # Get the data out of the file, split it into a list of people who have already RSVPed
        attendees = str(blob_client.download_blob().readall(), "utf-8")
        attendees = attendees.split("\n")

        if attendee not in attendees:
            attendees.append(attendee)
        
            # Make the local file
            with open(local_file, "w") as download_file:
                download_file.writelines("\n".join(attendees))

            # Push the local file to Azure blob
            with open(local_file, "rb") as data:
                blob_client.delete_blob()
                blob_client.upload_blob(data)

    # The blob wasn't there, oh no!
    except ResourceNotFoundError:
        # If the file doesn't exist, make a local file, conatining the single attendee from the request
        with open(local_file, "w") as f:
            f.write(attendee)

        # Write the file to Azure blob
        with open(local_file, "rb") as data:
            blob_client.upload_blob(data)




if __name__ == '__main__':
    # sync_blob("test event", "Jen")
    app.run(debug=True, use_reloader=True, host='0.0.0.0', port=8080)