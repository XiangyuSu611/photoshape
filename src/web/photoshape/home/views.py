from django.shortcuts import render
from django.http import HttpResponse
from .forms import UploadedImageForm
from .forms import UploadedImageForm2
from .models import Material, UploadedImage
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../terial/classifier/inference')
# sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../../data/json')
import infer_one_web 
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../terial/')
import match_models
from pathlib import Path
from PIL import Image
import PIL.ImageOps 
import json
from django.views.decorators.csrf import csrf_exempt
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../../thirdparty/rendkit/meshkit/')
import wavefront
import json
from django.template.loader import render_to_string
# Create your views here.

@csrf_exempt
def homepage(request):
	if request.method == 'POST':
		result = request.POST.get('result')
		form_id = request.POST.get('form_id')
		if result is not None and form_id is not None:
			try:
				img = UploadedImage.objects.get(pk=form_id)
				img.user_material = Material.objects.get(pk=result)
				img.save()
				return render(request, 'homepage.html', {'content': 'Your result has been submitted!'})
			except UploadedImage.DoesNotExist:
				return render(request, 'homepage.html', {'content': "Error: Object doesn't exist in dataset"})


	return render(request, 'homepage.html')

def homepage2(request):
        if request.method == 'POST':
                result = request.POST.get('result')
                form_id = request.POST.get('form_id')
                if result is not None and form_id is not None:
                        try:
                                img = UploadedImage.objects.get(pk=form_id)
                                img.user_material = Material.objects.get(pk=result)
                                img.save()
                                return render(request, 'homepage2.html', {'content': 'Your result has been submitted!'})
                        except UploadedImage.DoesNotExist:
                                return render(request, 'homepage2.html', {'content': "Error: Object doesn't exist in dataset"})


        return render(request, 'homepage2.html')

@csrf_exempt
def display_models(request):
	print(request.POST)
	print(request.FILES)
	original = 'original/chair1.png'
	#models = find_match_models(original)
	#return render(request, 'models.html')	

@csrf_exempt
def display_results2(request):
	if (request.method == 'POST'):
		print(request.POST)
		print(request.FILES)
		form = UploadedImageForm2(request.POST, request.FILES)
		if form.is_valid():
			form.save()   
			original = form.instance.original.name
			mask = form.instance.mask.name
			context={'url':form.instance.original.url}
			materials = infer_results(original, mask)
			# create or get Material instance
			for m_id, name in materials:
				m, _ = Material.objects.get_or_create(mid=m_id)
				form.instance.computed_materials.add(m)
			context['materials'] = materials
			context['form'] = form.instance.pk
			return HttpResponse(json.dumps(context))
		else:
			print(form.errors)
			print(form.non_field_errors())
			return HttpResponse(form.errors)

@csrf_exempt
def display_results(request):
	print(request.POST)
	print(request.FILES)

	if request.is_ajax():
		form = UploadedImageForm(request.POST, request.FILES)
		if form.is_valid():
			form.save()   
			original = form.instance.original.name
			s_id, phi, theta = find_match_models(original)

			#context['form'] = form.instance.pk

			mesh = wavefront.read_obj_file('/data/photoshape/blobs/shapes/'+ s_id +'/original.obj')
			materials = []
			for idx, material in enumerate(mesh.materials):
				materials.append((material, (idx+1)*20))
		
			html = render_to_string('models.html', {'models': [(s_id, phi, theta, mesh.bounding_size())], 'materials': materials, 'url':form.instance.original.url, 'name':original})
	
		else:
			print(form.errors)
			print(form.non_field_errors())
			html = render_to_string('models.html')
	

	#return render(request, 'models.html', {'models': [(3825, 1.33, 4.58, mesh.bounding_size())], 'materials': materials})
	
	
		return HttpResponse(html)

	return render(request, 'models.html')

def infer_results(original, mask):
	current_path = os.path.dirname(os.path.abspath(__file__))
	image_path = Path(current_path + '/../images/'+ original)
	mask_path = Path(current_path + '/../images/'+ mask)
	checkpoint_path= Path(current_path + '/../../../../data/classifier/model/model_best.pth.tar')

	res = mask.split(".");
	if len(res) > 0 and res[-1] != 'png':
		new_name = ''.join(res[:-1])
		new_name += '.png'
		new_mask_path = Path(current_path + '/../images/'+ new_name)
		os.rename(mask_path, new_mask_path)
		mask_path = new_mask_path

	image = Image.open(mask_path)

	if image.mode == 'RGBA':
	    r,g,b,a = image.split()
	    rgb_image = Image.merge('RGB', (r,g,b))

	    inverted_image = PIL.ImageOps.invert(rgb_image)
	    inverted_image = PIL.ImageOps.invert(inverted_image)

	    r2,g2,b2 = inverted_image.split()

	    final_transparent_image = Image.merge('RGBA', (r2,g2,b2,a))

	    final_transparent_image.save(mask_path)

	else:
	    inverted_image = PIL.ImageOps.invert(image)
	    inverted_image.save(mask_path)

	img = Image.open(Path(current_path + '/../images/mask/black.png'))
	layer = Image.open(mask_path) # this file is the transparent one
	img.paste(layer, (0,0), mask=layer) 
	# the transparancy layer will be used as the mask
	img.save(mask_path)

	result = infer_one_web.start_infer(image_path, mask_path, checkpoint_path)

	with open(current_path + '/../../../../data/json/materials.json') as f:
		data = json.load(f)

	materials = []
	for material in result['material'][:5]:
		m_id = material['id']
		# m_substance = material['pred_substance']
		# m_url = '/images/materials/' + str(m_id) + '/images/previews/bmps.png'
		m_name = data[str(m_id)]['name']
		materials.append((m_id, m_name))
	return materials

def find_match_models(original):
	models = []
	current_path = os.path.dirname(os.path.abspath(__file__))
	image_path = current_path + '/../images/'+ original
	pairs = match_models.compute_pair(image_path)
	for pair in pairs[:1]:
		return str(pair.shape_id), pair.elevation, pair.azimuth
		#models.append((str(pair.shape_id), pair.elevation, pair.azimuth))
	return 

