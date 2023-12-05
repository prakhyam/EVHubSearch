from bson.errors import InvalidId
import math
from flask import Flask, request, jsonify, g
from urllib.parse import quote_plus
from pymongo import MongoClient
from geojson import Point
from flask_cors import CORS 
from flask import Flask
import requests
from bson import ObjectId
from flask import Flask, request, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash


# Create a Flask application
app = Flask(__name__)
CORS(app)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:4200"}})


# Define the MongoDB client as a global variable
client =  MongoClient('mongodb://localhost:27017/')

def get_Lat_Long(location_query):
    print('making API call to Google for zipcode', location_query)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location_query}&key=AIzaSyASXpcjSKFL5Q50cxYcyNc-xRlHTrFp5EA"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['results']:
            latitude = data['results'][0]['geometry']['location']['lat']
            longitude = data['results'][0]['geometry']['location']['lng']
            return latitude, longitude
    return None, None

@app.route('/getStations', methods=['GET'])
def fetch_stations():
    stationID = 1583 

    if stationID is None:
        return jsonify({"error": "Station ID not provided"}), 400

    db = client['ev_station_db']
    collection = db['ev_stations']

    query = {'ID': stationID}
    station = collection.find_one(query)

    if station:
        # Process the station data
        processed_station = {
            "City": station.get("City"),
            "State": station.get("State"),
            "ZIP": station.get("ZIP"),
            "Latitude": station.get("Latitude"),
            "Longitude": station.get("Longitude"),
            "Station_Name": station.get("Station Name"),
            "Address": station.get("Street Address"),
            "Num_Level_2": None if math.isnan(station.get("EV Level2 EVSE Num", math.nan)) else station["EV Level2 EVSE Num"],
            "Num_level_1": None if math.isnan(station.get("EV Level1 EVSE Num", math.nan)) else station["EV Level1 EVSE Num"]
        }

        return jsonify(processed_station)
    else:
        return jsonify({"error": "Station not found"}), 404




# Define the /search endpoint route
@app.route('/search', methods=['GET'])
def search_stations():
    #zipcode = request.args.get('zipcode')
    station_name = request.args.get('stationName')
    location_query = request.args.get('location') 
    encoded_location = quote_plus(location_query)
    latitude, longitude = get_Lat_Long(location_query)
    print('searching coordinates for ZIP', location_query)
    print(latitude, longitude)
    radius_meters = 2000  # Specify the radius in meters for your search
    if latitude is None or longitude is None:
        return jsonify({"error": "Unable to find location for the given zipcode"}), 400
    

    # Use the 'client' global variable to access the MongoDB connection
    db = client['ev_station_db']
    collection = db['ev_stations']

    query = {}
    if location_query:
        encoded_location = quote_plus(location_query)
        latitude, logitude = get_Lat_Long(location_query)
        print('searching coordinates for ZIP', location_query)
        print(latitude, longitude)

        if latitude is None or longitude is None:
            return jsonify({"error": "Unable to find location for the given zipcode"}), 400

        location = Point((longitude, latitude))

        collection.create_index([("location", "2dsphere")])

        query["location"]={
            "$nearSphere":{
                "$geometry": location,
                "$maxDistance": radius_meters
            }
        }
    if station_name:
        query["$or"]== [{"Station Name": {"$regex": station_name, "$options": "i"}}]

    result= collection.find(query)

    # Create a GeoJSON Point with the coordinates
    location = Point((longitude, latitude))

    # Ensure that a 2dsphere index is created for the 'location' field
    collection.create_index([("location", "2dsphere")])

    # Perform the geo-spatial query to find stations within the specified radius
    result = collection.find({
        "location": {
            "$nearSphere": {
                "$geometry": location,
                "$maxDistance": radius_meters
            }
        }
    })
    # for doc in result:
    #     print(doc)

    # Prepare the response data
    stations = []
    for record in result:
        station_info = {
            "City": record["City"],
            "State": record["State"],
            "ZIP": record["ZIP"],
            "Latitude": record["Latitude"],
            "Longitude": record["Longitude"],
            "Station_Name": record["Station Name"],
            "Address": record["Street Address"],
            "Num_Level_2": None if math.isnan(record["EV Level2 EVSE Num"]) else record["EV Level2 EVSE Num"],
            "Num_level_1": None if math.isnan(record["EV Level1 EVSE Num"]) else record["EV Level1 EVSE Num"],
        }
        stations.append(station_info)
    return jsonify(stations)


# @app.route('/stations/<station_id>/maintenance', methods=['PATCH'])
# def update_maintenance(station_id):
#     # Parse the JSON data from the request
#     data = request.get_json()

#     # Extract the maintenance status from the request data
#     maintenance_status = data.get('maintenance', None)

#     # Check if the maintenance status is provided
#     if maintenance_status is None:
#         return jsonify({"error": "Maintenance status not provided"}), 400

#     # Use the 'client' global variable to access the MongoDB connection
#     db = client['ev_station_db']
#     collection = db['ev_stations']

#     # Query using the 'ID' field
    
#     result = collection.update_one(
#         {"ID": int(station_id)},  # Match the station by its ID
#         {
#             "$set": {
#                 "maintenance": maintenance_status,
#                 "availability": not maintenance_status
#             }
#         }
#     )

#     # Check if the update was successful
#     if result.matched_count == 0:
#         return jsonify({"error": "Station not found"}), 404
#     elif result.modified_count == 0:
#         return jsonify({"error": "Station status not modified"}), 409

#     # Return success message
#     return jsonify({"success": True, "message": "Station maintenance status updated"}), 200


@app.route('/stations/<station_id>/maintenance', methods=['PATCH'])
def update_maintenance(station_id):
    data = request.get_json()
    maintenance_status = data.get('maintenance', None)

    if maintenance_status is None:
        return jsonify({"error": "Maintenance status not provided"}), 400

    try:
        db = client['ev_station_db']
        collection = db['ev_stations']

        # Ensure station_id is an integer as it is in MongoDB
        station_id_int = int(station_id)

        # Update the maintenance status in MongoDB
        result = collection.update_one(
            {"ID": station_id_int},
            {"$set": {"maintenance": maintenance_status}}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Station not found"}), 404
        elif result.modified_count == 0:
            return jsonify({"error": "No update made"}), 304  # Or another appropriate status code

        return jsonify({"success": True, "message": "Station maintenance status updated"}), 200

    except Exception as e:
        print(f"Error updating maintenance status: {e}")
        return jsonify({"error": str(e)}), 500



# Run the Flask application
if __name__ == '__main__':
    try:
        app.run(debug=True, host='0.0.0.0', port=5001)
    finally:
        client.close()