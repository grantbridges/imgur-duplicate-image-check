import os
import json
import glob
import hashlib
import math
import requests
from datetime import datetime, timezone

# ** Imgur API Documentation: https://apidocs.imgur.com/?version=latest **

if not os.path.isfile("client-id.txt"):
    print("** No Client Id detected **")
    print("Register an Imgur application at https://api.imgur.com/oauth2/addclient and record the Client Id value in \"client-id.txt\" in your working directory.")
    os.system("pause")
    quit()

# ---

CLIENT_ID = open("client-id.txt", "r").read()
ACCOUNT_NAME = 'onlyporridge'

data_dir = os.getenv('LOCALAPPDATA') + '\\Imgur\\Duplicate Image Check\\data\\' + ACCOUNT_NAME + "\\"
images_dir = data_dir + "images\\"
images_data_filepath = data_dir + "images_data.json"

if not os.path.exists(data_dir):
    os.makedirs(data_dir)

if not os.path.exists(images_dir):
    os.makedirs(images_dir)

# ---
# Helper Methods

def get_account_images_count():
    url = "https://api.imgur.com/3/account/" + ACCOUNT_NAME +"/images/count"
    headers = {'Authorization': 'Client-ID ' + CLIENT_ID}

    print("Fetching images count for " + ACCOUNT_NAME + "...")
    response = requests.request("GET", url, headers=headers)

    if response.status_code == 200:
        data = json.loads(response.text.encode('utf8'))

        image_count = data['data']
        print("Found {0} images for {1}".format(image_count, ACCOUNT_NAME))
        return image_count
    else:
        print("Error - could not get images count for {0} ({1} - {2})".format(ACCOUNT_NAME, response.status_code, response.reason))
        return -1

def get_image_info(image_hash):
    url = "https://api.imgur.com/3/image/" + image_hash
    headers = {'Authorization': 'Client-ID ' + CLIENT_ID}

    print("Fetching image info for " + image_hash + "...")
    response = requests.request("GET", url, headers=headers)

    if response.status_code == 200:
        return json.loads(response.text.encode('utf8'))['data']
    else:
        print("Error - could not get image info for {0} ({1} - {2})".format(image_hash, response.status_code, response.reason))

    return None

def get_image_data_by_id(id, images_data):
    for d in images_data:
        if d['id'] == id:
            return d
    return None

def compute_file_hash(filepath):
    hasher = hashlib.md5()
    blocksize = 65536

    with open(filepath, 'rb') as file:
        buffer = file.read(blocksize)
        while len(buffer) > 0:
            hasher.update(buffer)
            buffer = file.read(blocksize)
    
    return hasher.hexdigest()

def load_images_data():
    if os.path.isfile(images_data_filepath):
        with open(images_data_filepath) as json_file:
            return json.load(json_file)
    else:
        return []

def save_images_data(images_data):
    open(images_data_filepath, 'w+').write(json.dumps(images_data))

def get_all_account_images_data(images_data):
    page_size = 50 # set by imgur
    images_count = get_account_images_count()

    if images_count != -1:
        print("Fetching images data for {0}...".format(ACCOUNT_NAME))

        page_count = math.ceil(images_count / page_size)

        current_page = 0
        while current_page <= page_count: 
            url = "https://api.imgur.com/3/account/{0}/images/{1}".format(ACCOUNT_NAME, current_page)
            headers = {'Authorization': 'Client-ID ' + CLIENT_ID}

            #print("  Fetching images data (page {0} of {1})...".format(current_page, page_count))
            response = requests.request("GET", url, headers=headers)

            if response.status_code == 200:
                data = json.loads(response.text.encode('utf8'))
                for entry in data['data']:
                    existing_entry = get_image_data_by_id(entry['id'], images_data)
                    if existing_entry == None:
                        images_data.append(entry)
            else:
                print("Error - failed to get images data on page {0} ({1} - {2})".format(current_page, response.status_code, response.reason))

            current_page += 1
        
    return images_data

def download_all_images(images_data):
    if len(images_data) == 0:
        return

    print("Starting download of all images for {0}...".format(ACCOUNT_NAME))

    for i in range(0, len(images_data)):
        data = images_data[i]

        img_url = data['link']
        filename = os.path.split(img_url)[1]
        filename = filename.split("?")[0] # sometimes there's a "?#" prefix
        
        if filename in os.listdir(images_dir):
            #print("  Skipping {0} - already downloaded ({1} of {2})".format(filename, i+1, len(images_data)))
            continue

        print("  Downloading {0} ({1} of {2})".format(filename, i+1, len(images_data)))
        
        response = requests.request("GET", img_url)
        if response.status_code == 200:
            open(images_dir + filename, 'wb').write(response.content)
        else:
            print("Error - could not open image url '{0}' ({1} - {2})".format(img_url, response.status_code, response.reason))

def compute_hashes_and_check(images_data):
    files = glob.glob(images_dir + "\\*.*")

    if len(files) == 0:
        return

    # compute hashes over all files in images_dir
    print("Computing hashes...")
    for i in range(0, len(files)):
        file = files[i]
        file_name = os.path.split(file)[1]
        id = file_name.split(".")[0]
        
        data = get_image_data_by_id(id, images_data)
        if data == None:
            continue # have a file with no data about it?

        if 'hash' not in data or data['hash'] == '':
            #print("  Computing hash for {0} ({1} of {2})...".format(file_name, i+1, len(files)))
            data['hash'] = compute_file_hash(file)
        
    # check for duplicates
    print("Checking for duplicates...")
    for i in range(0, len(images_data)):
        base_data = images_data[i]

        for j in range(i+1, len(images_data)):
            check_data = images_data[j]
            
            if base_data['hash'] == check_data['hash']:
                image_1_upload_time = datetime.fromtimestamp(base_data['datetime'], timezone.utc)
                image_2_upload_time = datetime.fromtimestamp(check_data['datetime'], timezone.utc)

                print("  Duplicates found:")
                print("    {0}: {1}".format(base_data['id'], str(image_1_upload_time)))
                print("    {0}: {1}".format(check_data['id'], str(image_2_upload_time)))

# ---
# Main Program

# load existing images data, if we have it
images_data = load_images_data()

# update images data with data from imgur server
get_all_account_images_data(images_data)

# download any images we don't already have
download_all_images(images_data)

# compute hashes over all images and check for any duplicates
compute_hashes_and_check(images_data)

# save updated images data back out
save_images_data(images_data)

os.system("pause")