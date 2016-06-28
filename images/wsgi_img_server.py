#!/bin/python

import os
from flask import Flask, Response, request, abort, render_template_string, send_from_directory
import Image
import StringIO

app = Flask(__name__)

WIDTH = 1000
HEIGHT = 800

TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title></title>
    <meta charset="utf-8" />
    <style>
body {
    margin: 0;
    background-color: #333;
}

.image {
    display: block;
    margin: 2em auto;
    background-color: #444;
    box-shadow: 0 0 10px rgba(0,0,0,0.3);
}

img {
    display: block;
}
    </style>
    <script src="https://code.jquery.com/jquery-1.10.2.min.js" charset="utf-8"></script>
    <script src="http://luis-almeida.github.io/unveil/jquery.unveil.min.js" charset="utf-8"></script>
    <script>
$(document).ready(function() {
    $('img').unveil(1000);
});
    </script>
</head>
<body>
    <table>
    {% for image in images %}
        {% if i == 0 %}
        <tr>
        {% endif %}
        <td><a class="image" href="{{ image.src }}" style="width: {{ image.width }}px; height: {{ image.height }}px">
            <img src="{{ image.src }}" width="{{ image.width }}" height="{{ image.height }}" />
        </a></td>
        {% if i == 2 %}
        </tr>
        {% set i = -1%}
        {% endif %}
        {% set i = i + 1 %}
    {% endfor %}
</body>
'''

@app.route('/<path:filename>')
def image(filename):
    try:
        w = int(request.args['w'])
        h = int(request.args['h'])
    except (KeyError, ValueError):
        return send_from_directory('.', filename)

    try:
        im = Image.open(filename)
        im.thumbnail((w, h), Image.ANTIALIAS)
        io = StringIO.StringIO()
        im.save(io, format='JPEG')
        return Response(io.getvalue(), mimetype='image/jpeg')

    except IOError:
        abort(404)

    return send_from_directory('.', filename)

@app.route('/')
def index():
    images = []
    file_paths = []
    for root, dirs, files in os.walk('.'):
        for filename in [os.path.join(root, name) for name in files]:
            if not filename.endswith('.jpg'):
                continue
            if "raw" in filename:
                continue
            file_paths.append(filename)
            print filename
    file_paths.sort(key=lambda x: os.stat(x).st_mtime, reverse=True)
    for sorted_filename in file_paths:
        im = Image.open(sorted_filename)
        w, h = im.size
        aspect = 1.0*w/h
        if aspect > 1.0*WIDTH/HEIGHT:
            width = min(w, WIDTH)
            height = width/aspect
        else:
            height = min(h, HEIGHT)
            width = height*aspect
        images.append({
            'width': int(width),
            'height': int(height),
            'src': sorted_filename
        })
    i = 0
    return render_template_string(TEMPLATE, **{
        'images': images,
        'i': i
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8000)
