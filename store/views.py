from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from .models import Product
from decimal import Decimal
import stripe
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
stripe.api_key = settings.STRIPE_SECRET_KEY

def product_list(request):
    products = Product.objects.all()
    return render(request, 'store/product_list.html', {'products': products})

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = request.session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    request.session['cart'] = cart
    return redirect('cart_detail')

def cart_detail(request):
    cart = request.session.get('cart', {})
    total = Decimal('0')
    cart_items = []
    for product_id, quantity in cart.items():
        product = get_object_or_404(Product, id=product_id)
        subtotal = product.price * quantity
        total += subtotal
        cart_items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    return render(request, 'store/cart_detail.html', {'cart_items': cart_items, 'total': total})


def checkout(request):
    if request.method == 'POST':
        # Create Stripe Checkout Session
        domain_url = 'http://127.0.0.1:8000/'  # Change to your domain in prod (e.g., https://yourapp.com)
        stripe.api_key = settings.STRIPE_SECRET_KEY

        cart = request.session.get('cart', {})
        line_items = []
        total = Decimal('0')
        for product_id, quantity in cart.items():
            product = get_object_or_404(Product, id=product_id)
            subtotal = product.price * quantity
            total += subtotal
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name,
                    },
                    'unit_amount': int(product.price * 100),  # Cents
                },
                'quantity': quantity,
            })

        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=domain_url + 'success/?session_id={CHECKOUT_SESSION_ID}',  # Points to /success/
                cancel_url=domain_url + 'cancel/',  # Points to /cancel/
            )
            # Clear cart after session creation (or on webhook success)
            request.session['cart'] = {}
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            return render(request, 'store/checkout_error.html', {'error': str(e)})

    # GET: Show checkout form
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('product_list')
    total = sum(
        get_object_or_404(Product, id=pid).price * qty
        for pid, qty in cart.items()
    )
    return render(request, 'store/checkout.html', {
        'total': total,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    })

def checkout_success(request):
    session_id = request.GET.get('session_id')
    if session_id:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        # Optional: Log or email based on stripe_session['payment_intent']
        print(f"Payment confirmed: {stripe_session['payment_status']}")
    return render(request, 'store/checkout_success.html')  # Renders success template

def checkout_cancel(request):
    return render(request, 'store/checkout_cancel.html')  # Renders cancel template

@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    if event['type'] == 'checkout.session.completed':
        # Fulfillment: e.g., send email, update order
        session = event['data']['object']
        # Access customer email: session['customer_details']['email']
        print(f"Payment succeeded for {session['customer_details']['email']}")

    return JsonResponse({'status': 'success'})
