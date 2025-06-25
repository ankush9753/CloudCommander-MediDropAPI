from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import pymysql
import boto3
import uuid

app = Flask(__name__)
CORS(app)

# AWS S3 configuration
S3_BUCKET = 'mytestbucketankush'
S3_REGION = 'ap-south-1'
AWS_ACCESS_KEY = 'AKIARJBSWWHSXASCDVXQ'
AWS_SECRET_KEY = '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'

s3_client = boto3.client(
    's3',
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# AWS MySQL connection settings
DB_HOST = 'databaseinstance.c1wsgkys068n.ap-south-1.rds.amazonaws.com'
DB_USER = 'admin'
DB_PASSWORD = 'Admin#12345678'
DB_Database = 'MyDB'


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    connection = pymysql.connect(
        host=DB_HOST,
        user= DB_USER,
        password=DB_PASSWORD,
        database=DB_Database,
        cursorclass=pymysql.cursors.DictCursor 
    )
    cursor = connection.cursor()
    query = "SELECT UserId FROM User WHERE UserName=%s AND Password=%s"
    cursor.execute(query, (username, password))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    print(result)
    if result:
        return jsonify({"success": True, "userId": result['UserId']}), 200
    return jsonify({"success": False, "message": "Invalid credentials"}), 401
    


@app.route('/api/records', methods=['GET'])
def get_records():
    user_id = request.args.get('userId')
    print(user_id)
    if not user_id:
         return jsonify({"success": False, "message": "Missing userId"}), 400

    connection = pymysql.connect( 
        host=DB_HOST,
        user= DB_USER,
        password=DB_PASSWORD,
        database=DB_Database
        )
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT r.RecordId, CONCAT(u.FirstName, ' ' ,u.LastName ) as patientname, r.Filename, r.Fileurl FROM Records r INNER JOIN User u on r.UserId = u.UserId WHERE r.UserId = %s", (user_id,))
    records = cursor.fetchall()
    cursor.close()
    connection.close()
    return jsonify(records), 200
    

@app.route('/api/records', methods=['POST'])
def upload_record():
    
    try:
        file = request.files.get('document')
        userId = request.form.get('userId')
    
        if not userId or not file:
            return jsonify({"success": False, "message": "Missing data"}), 400

        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        print(file, userId, filename, unique_filename )
        s3_client.upload_fileobj(
                file,
                S3_BUCKET,
                unique_filename
            )
        fileurl = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{unique_filename}"
        connection = pymysql.connect(
                host=DB_HOST,
                user= DB_USER,
                password=DB_PASSWORD,
                database=DB_Database,
            )
        cursor = connection.cursor()
        insert_query = "INSERT INTO Records (UserId, Filename, FileUrl, FileS3Key) VALUES (%s, %s, %s, %s)"
        cursor.execute(insert_query, (userId, filename, fileurl, unique_filename))
        connection.commit()
        cursor.close()
        connection.close()
        return jsonify({"success": True, "fileUrl": fileurl}), 201

    except Exception as e:
         return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    print(record_id)
    try:
        connection = pymysql.connect(
                host=DB_HOST,
                user= DB_USER,
                password=DB_PASSWORD,
                database=DB_Database,
                cursorclass=pymysql.cursors.DictCursor 
            )
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT FileS3Key FROM Records WHERE RecordId = %s", (record_id,))
        record = cursor.fetchone()

        if record:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=record['FileS3Key'])
                cursor.execute("DELETE FROM Records WHERE RecordId = %s", (record_id,))
                connection.commit()
                cursor.close()
                connection.close()
                return jsonify({"success": True}), 200
        else:
                return jsonify({"success": False, "message": "Record not found"}), 404        

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)