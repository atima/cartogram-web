#!/usr/bin/env python
import geojson_extrema, awslambda
import settings

import json
import datetime
from flask import Flask, request, Response, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from handler import CartogramHandler
from asset import Asset
from views import contact, tracking, custom_captcha

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    Asset(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    limiter = Limiter(get_remote_address, app=app, default_limits=["50 per hour"], 
                    storage_uri='redis://{}:{}'.format(settings.CARTOGRAM_REDIS_HOST, settings.CARTOGRAM_REDIS_PORT))

    app.app_context().push()
    app.secret_key = 'LTTNWg8luqfWKfDxjFaeC3vYoGrC2r2f5mtXo5IE/jt1GcY7/JaSq8V/tB'
    app.config['SQLALCHEMY_DATABASE_URI'] = settings.DATABASE_URI
    # This gets rid of an annoying Flask error message. We don't need this feature anyway.
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['ENV'] = 'development' if settings.DEBUG else 'production'

    # Whenever you make changes to the DB models, you must run commands as follows:
    # export FLASK_APP=web.py
    # flask db migrate -m "Migration log."
    # flask db upgrade
    if settings.USE_DATABASE:
        db.init_app(app)
        migrate = Migrate(app, db)

        class CartogramEntry(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            string_key = db.Column(db.String(32), unique=True, nullable=False)
            date_created = db.Column(db.DateTime(), nullable=False)
            date_accessed = db.Column(db.DateTime(), server_default='0001-01-01 00:00:00')        
            handler = db.Column(db.String(100), nullable=False)
            cartogramui_data = db.Column(db.UnicodeText(), nullable=False)

            def __repr__(self):
                return '<CartogramEntry {}>'.format(self.string_key)
            
        db.create_all()

    default_cartogram_handler = 'usa'
    cartogram_handler = CartogramHandler()

    @app.route('/', methods=['GET'])
    def index():
        return render_template('welcome.html', page_active='home', tracking=tracking.determine_tracking_action(request))


    @app.route('/about', methods=['GET'])
    def about():
        return render_template('about.html', page_active='about', tracking=tracking.determine_tracking_action(request))


    @app.route('/cookies', methods=['GET'])
    def cookies():
        return render_template('cookies.html', page_active='', tracking=tracking.determine_tracking_action(request))


    @app.route('/faq', methods=['GET'])
    def faq():
        return render_template('faq.html', page_active='faq', tracking=tracking.determine_tracking_action(request))


    @app.route('/tutorial', methods=['GET'])
    def tutorial():
        return render_template('tutorial.html', page_active='tutorial', tracking=tracking.determine_tracking_action(request))


    app.add_url_rule('/contact', methods=['GET', 'POST'], view_func=contact.contact)
    app.add_url_rule('/api/v1/consent', methods=['POST'], view_func=tracking.consent)
    app.add_url_rule('/api/v1/gencaptcha', methods=['GET'], view_func=custom_captcha.gencaptcha)


    @app.route('/cartogram', methods=['GET'])
    def get_cartogram():
        return get_cartogram_by_name(default_cartogram_handler, None)


    @app.route('/cartogram/map/<map_name>', methods=['GET'], defaults={'mode': None})
    @app.route('/cartogram/map/<map_name>/<mode>', methods=['GET'])
    def get_cartogram_by_name(map_name, mode):
        if mode == 'embed':
            template = 'embed.html'
        else:
            template = 'cartogram.html'

        if not cartogram_handler.has_handler(map_name):
            return Response('Cannot find the map {}'.format(map_name), status=500)

        return render_template(template, page_active='cartogram', 
                            maps=cartogram_handler.get_sorted_handler_names(),
                            map_name=map_name,
                            mode=mode, tracking=tracking.determine_tracking_action(request))

    @app.route('/cartogram/key/<string_key>', methods=['GET'], defaults={'mode': None})
    @app.route('/cartogram/key/<string_key>/<mode>', methods=['GET'])
    def cartogram_by_key(string_key, mode):
        if mode == 'embed':
            template = 'embed.html'
        else:
            template = 'cartogram.html'

        if not settings.USE_DATABASE:
            return Response('Not found', status=404)

        cartogram_entry = CartogramEntry.query.filter_by(string_key=string_key).first_or_404()

        if cartogram_entry is None or not cartogram_handler.has_handler(cartogram_entry.handler):
            return Response('Error', status=500)
        
        cartogram_entry.date_accessed = datetime.datetime.now(datetime.UTC)
        db.session.commit()    

        return render_template(template, page_active='cartogram', 
                            maps=cartogram_handler.get_sorted_handler_names(),
                            map_name=cartogram_entry.handler, map_data_key=string_key,
                            mode=mode, tracking=tracking.determine_tracking_action(request))

    @app.route('/api/v1/getprogress', methods=['GET'])
    @limiter.exempt
    def getprogress():
        current_progress_output = awslambda.getprogress(request.args['key'])
        return Response(json.dumps(current_progress_output), status=200, content_type='application/json')

    def cartogram_rate_limit():
        return settings.CARTOGRAM_RATE_LIMIT

    @app.route('/api/v1/cartogram', methods=['POST'])
    @limiter.limit(cartogram_rate_limit)
    def cartogram():    
        colName = 0
        colColor = 1
        colValue = 2 # Starting column of data
        print(request.form)

        try:
            data = json.loads(request.form['data'])
            handler = data['handler']

            if 'handler' not in data or not cartogram_handler.has_handler(handler):
                return Response('{"error":"The handler was invaild."}', status=400, content_type='application/json')

            if 'stringKey' not in data:
                return Response('{"error":"Missing sharing key."}', status=404, content_type='application/json')

            string_key = data['stringKey']
            cart_data = cartogram_handler.get_area_string_and_colors(handler, data)
            lambda_result = awslambda.generate_cartogram(cart_data[0],
                                cartogram_handler.get_gen_file(handler), settings.CARTOGRAM_LAMBDA_URL,
                                settings.CARTOGRAM_LAMDA_API_KEY, string_key)

            cartogram_gen_output = lambda_result['stdout']
            cartogram_json = json.loads(cartogram_gen_output)

            if lambda_result['world'] == False:
                cartogram_json = cartogram_json['Original']

            if 'bbox' not in cartogram_json:
                cartogram_json['bbox'] = geojson_extrema.get_extrema_from_geojson(cartogram_json)
                
            cartogram_json['tooltip'] = cart_data[2]
            
            if 'persist' in data:
                with open('static/userdata/{}.json'.format(string_key), 'w') as outfile:
                    outfile.write(json.dumps({'{}-custom'.format(colValue): cartogram_json}))
                
                if settings.USE_DATABASE:
                    new_cartogram_entry = CartogramEntry(string_key=string_key, date_created=datetime.datetime.today(),
                                            date_accessed=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=365),
                                            handler=handler, cartogramui_data=json.dumps({'colors': cart_data[1]}))
                    db.session.add(new_cartogram_entry)
                    db.session.commit()        
            else:
                string_key = None

            return get_mappack_by_userdata(handler, 
                                        {'colors': cart_data[1], 'stringKey': string_key}, 
                                        {'{}-custom'.format(colValue): cartogram_json})
        
        # except (KeyError, csv.Error, ValueError, UnicodeDecodeError):
        #     return Response('{"error":"The data was invalid."}', status=400, content_type='application/json')
        except Exception as e:
            print(e)
            return Response('{"error": "The data may be invalid or the process has timed out. Please try again later."}', status=400, content_type='application/json')  

    @app.route('/api/v1/mappack/<string_key>', methods=['GET'])
    def get_mappack_by_key(string_key):
        if not settings.USE_DATABASE:
            return Response('Not found', status=404)

        cartogram_entry = CartogramEntry.query.filter_by(string_key=string_key).first_or_404()

        if cartogram_entry == None or not cartogram_handler.has_handler(cartogram_entry.handler):
            return Response('Error', status=500)
        
        cartogram_entry.date_accessed = datetime.datetime.now(datetime.UTC)
        db.session.commit()        
        
        with open('static/userdata/{}.json'.format(cartogram_entry.string_key), 'r') as file:
            new_maps = json.load(file)

        mappack = json.loads(cartogram_entry.cartogramui_data)       
        mappack['stringKey'] = string_key

        return get_mappack_by_userdata(cartogram_entry.handler, mappack, new_maps)

    def get_mappack_by_userdata(handler, mappack, new_maps):    
        with open('static/cartdata/{}/mappack.json'.format(handler), 'r') as file:
            original_mappack = json.load(file)
        
        mappack.update(new_maps) 
        data_names = list(new_maps.keys())

        if not 'config' in original_mappack:
            mappack['config'] = {}
        elif 'data_names' in original_mappack['config']:
            base_name = original_mappack['config']['data_names'][0]
        else:
            base_name = 'original'

        for item in ['abbreviations', 'config', 'labels', base_name]:
            if item in original_mappack:
                mappack[item] = original_mappack[item]

        mappack['colors'] = {**original_mappack['colors'], **mappack['colors']}

        data_names.insert(0, base_name)        
        mappack['config']['data_names'] = data_names

        return Response(json.dumps(mappack), content_type='application/json', status=200)

    @app.route('/cart/<key>', methods=['GET'])
    @app.route('/embed/map/<key>', methods=['GET'])
    @app.route('/embed/cart/<key>', methods=['GET'])
    def cartogram_old(key):
        return render_template('404_code_expired.html', title = 'Outdated share/embed code'), 404


    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=settings.DEBUG, host=settings.HOST, port=settings.PORT)
