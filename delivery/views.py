import random
import os
from mailjet_rest import Client

from django.conf import settings
from decimal import Decimal
from django.db import transaction
from django.views.decorators.http import require_POST
import razorpay
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, redirect
from datetime import datetime
from django.db.models import Exists, OuterRef
from django.contrib.auth.hashers import make_password, check_password
from django.shortcuts import get_object_or_404
from .models import Address, Cart, CartItem, Customer, Favorite, Item, Order, OrderItem, Restaurant

def send_otp_email(subject, message, recipient):
    if os.environ.get("RENDER") == "true":
        api_key = os.environ.get("MAILJET_API_KEY")
        api_secret = os.environ.get("MAILJET_SECRET_KEY")
        sender_email = os.environ.get(
            "MAILJET_SENDER_EMAIL",
            "cravecart001@gmail.com"
        )

        if not api_key or not api_secret:
            raise RuntimeError("Mailjet API credentials are not configured.")

        mailjet = Client(
            auth=(api_key, api_secret),
            version="v3.1"
        )

        data = {
            "Messages": [
                {
                    "From": {
                        "Email": sender_email,
                        "Name": "CraveCart"
                    },
                    "To": [
                        {
                            "Email": recipient
                        }
                    ],
                    "Subject": subject,
                    "TextPart": message
                }
            ]
        }

        result = mailjet.send.create(data=data)

        if result.status_code not in (200, 201):
            raise RuntimeError(
                f"Mailjet email failed: {result.status_code} "
                f"{result.text}"
            )

        return True

    # Keep Gmail SMTP for local development
    return send_mail(
        subject,
        message,
        None,
        [recipient],
    )

def index(request):
    return render(request, 'delivery/index.html')


def open_signup(request):
    return render(request, 'delivery/signup.html')

def signup(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        address = request.POST.get('address') or ''
        
        # Check whether email is already registered
        if Customer.objects.filter(email__iexact=email).exists():
            return render(request, 'delivery/signup.html', {
        'error': 'This email is already registered.',
        'username': username,
        'email': email,
        'mobile': mobile,
        'address': address
    })

        if Customer.objects.filter(mobile=mobile).exists():
            return render(request, 'delivery/signup.html', {
        'error': 'This mobile number is already registered.',
        'username': username,
        'email': email,
        'mobile': mobile,
        'address': address
    })

        # Generate 6-digit OTP
        otp = str(random.randint(100000, 999999))

        # Store signup information temporarily
        request.session['signup_username'] = username
        request.session['signup_password'] = password
        request.session['signup_email'] = email
        request.session['signup_mobile'] = mobile
        request.session['signup_address'] = address

        # Store OTP
        request.session['signup_otp'] = otp

        # OTP expiry: 5 minutes
        request.session['signup_otp_expiry'] = (
            timezone.now() + timedelta(minutes=5)
        ).isoformat()

        # Send OTP
        send_otp_email(
            'CraveCart Email Verification',
            f'Your CraveCart verification OTP is: {otp}\n\n'
            'This OTP is valid for 5 minutes.',
            email,
        )

        messages.success(
              request,
            'OTP sent successfully to your email address.'
        )

        return redirect('verify_otp')

    return render(request, 'delivery/signup.html')

def verify_otp(request):

    if request.method == 'POST':

        entered_otp = request.POST.get('otp')

        saved_otp = request.session.get('signup_otp')
        expiry_time = request.session.get('signup_otp_expiry')

        # Check whether signup OTP exists
        if not saved_otp or not expiry_time:
            return render(request, 'delivery/verify_otp.html', {
                'error': 'OTP session expired. Please create your account again.'
            })

        # Check OTP expiry
        expiry_time = timezone.datetime.fromisoformat(expiry_time)

        if timezone.now() > expiry_time:

            # Remove expired OTP
            request.session.pop('signup_otp', None)
            request.session.pop('signup_otp_expiry', None)

            return render(request, 'delivery/verify_otp.html', {
                'error': 'OTP has expired. Please create your account again.'
            })

        # Check entered OTP
        if entered_otp != saved_otp:

            return render(request, 'delivery/verify_otp.html', {
                'error': 'Invalid OTP. Please enter the correct OTP.'
            })

        # OTP is correct
        username = request.session.get('signup_username')
        password = request.session.get('signup_password')
        email = request.session.get('signup_email')
        mobile = request.session.get('signup_mobile')
        address = request.session.get('signup_address', '')

        # Check that all required signup information exists
        if not all([username, password, email, mobile]):
            return render(request, 'delivery/verify_otp.html', {
                'error': 'Signup session expired. Please register again.'
            })

        # Prevent duplicate email registrations
        if Customer.objects.filter(email__iexact=email).exists():
             return render(request, 'delivery/verify_otp.html', {
                'error': 'This email is already registered.'
            })
             
        if Customer.objects.filter(mobile=mobile).exists():
            return render(request, 'delivery/verify_otp.html', {
        'error': 'This mobile number is already registered.'
    })

        # Create customer with a securely hashed password
        Customer.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            mobile=mobile,
            address=address,
            is_admin=False
        )
        # Remove temporary signup data

        request.session.pop('signup_username', None)

        request.session.pop('signup_password', None)

        request.session.pop('signup_email', None)

        request.session.pop('signup_mobile', None)

        request.session.pop('signup_address', None)

        request.session.pop('signup_otp', None)

        request.session.pop('signup_otp_expiry', None)

        messages.success(

             request,

             'OTP verified successfully. Your account has been created.'

        )

        return redirect('open_signin')

    return render(request, 'delivery/verify_otp.html')

def customer_home(request, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    restaurantList = get_active_restaurants()

    return render(request, 'delivery/customer_home.html', {
        'restaurantList': restaurantList,
        'username': customer.username
    })
    
def resend_otp(request):

    # Get email from signup session
    email = request.session.get('signup_email')

    # Check whether signup session still exists
    if not email:

        return redirect('open_signup')

    # Generate a new 6-digit OTP
    otp = str(random.randint(100000, 999999))

    # Store new OTP in session
    request.session['signup_otp'] = otp

    # Reset OTP expiry to 5 minutes
    request.session['signup_otp_expiry'] = (
        timezone.now() + timedelta(minutes=5)
    ).isoformat()

    # Send new OTP
    send_otp_email(
    'CraveCart Email Verification',
    f'Your new CraveCart verification OTP is: {otp}\n\n'
    'This OTP is valid for 5 minutes.',
    email,
)
    # Return to OTP page
    return redirect('verify_otp')



def open_signin(request):
    return render(request, 'delivery/signin.html')


def get_active_restaurants():
    vegetarian_items = Item.objects.filter(
        restaurant=OuterRef('pk'),
        vegetarian=True,
        available=True
    )

    return Restaurant.objects.filter(
        is_active=True
    ).annotate(
        has_vegetarian=Exists(vegetarian_items)
    )
    
def signin(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        password = request.POST.get('password') or ''

        customer = Customer.objects.filter(
            email__iexact=email
        ).first()

        if customer and check_password(password, customer.password):
            request.session.flush()

            request.session['customer_id'] = customer.id
            request.session['username'] = customer.username
            request.session['is_admin'] = customer.is_admin

            if customer.is_admin:
                return redirect('admin_home')

            return redirect(
                'customer_home',
                username=customer.username
            )

        return render(request, 'delivery/signin.html', {
            'error': 'Invalid email or password.',
            'email': email
        })

    return render(request, 'delivery/signin.html')

def forgot_password(request):

    if request.method == 'POST':

        email = request.POST.get('email')

        try:
            customer = Customer.objects.get(email=email)

        except Customer.DoesNotExist:

            return render(request, 'delivery/forgot_password.html', {
                'error': 'No account found with this email address.'
            })

        # Generate reset OTP
        otp = str(random.randint(100000, 999999))

        # Store email
        request.session['reset_email'] = email

        # Store OTP
        request.session['reset_otp'] = otp

        # OTP valid for 5 minutes
        request.session['reset_otp_expiry'] = (
            timezone.now() + timedelta(minutes=5)
        ).isoformat()

        # Send OTP
        send_otp_email(
            'CraveCart Password Reset OTP',
             f'Your CraveCart password reset OTP is: {otp}\n\n'
            'This OTP is valid for 5 minutes.',
            email,
        )

        messages.success(
            request,
            'OTP sent successfully to your email address.'
        ) 

        return redirect('verify_reset_otp')

    return render(request, 'delivery/forgot_password.html')

def reset_password(request):

    # OTP must be verified first
    if not request.session.get('reset_otp_verified'):
        return redirect('forgot_password')

    if request.method == 'POST':

        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:

            return render(request, 'delivery/reset_password.html', {
                'error': 'Passwords do not match.'
            })

        email = request.session.get('reset_email')

        if not email:
            return redirect('forgot_password')

        try:
            customer = Customer.objects.get(email=email)

        except Customer.DoesNotExist:

            return render(request, 'delivery/reset_password.html', {
                'error': 'Account not found.'
            })

        # Update password
        customer.password = make_password(new_password)
        customer.save()

        # Clear reset session
        request.session.pop('reset_email', None)
        request.session.pop('reset_otp', None)
        request.session.pop('reset_otp_expiry', None)
        request.session.pop('reset_otp_verified', None)

        messages.success(
            request,
            'Password updated successfully.'
        )

        return redirect('open_signin')

    return render(request, 'delivery/reset_password.html')

def verify_reset_otp(request):

    if request.method == 'POST':

        entered_otp = request.POST.get('otp')

        saved_otp = request.session.get('reset_otp')
        expiry_time = request.session.get('reset_otp_expiry')

        # Check whether reset OTP exists
        if not saved_otp or not expiry_time:
            return render(request, 'delivery/verify_reset_otp.html', {
                'error': 'OTP session expired. Please start the password reset again.'
            })

        # Convert expiry time
        expiry_time = timezone.datetime.fromisoformat(expiry_time)

        # Check OTP expiry
        if timezone.now() > expiry_time:

            request.session.pop('reset_otp', None)
            request.session.pop('reset_otp_expiry', None)

            return render(request, 'delivery/verify_reset_otp.html', {
                'error': 'OTP has expired. Please request a new OTP.'
            })

        # Check OTP
        if entered_otp != saved_otp:

            return render(request, 'delivery/verify_reset_otp.html', {
                'error': 'Invalid OTP. Please enter the correct OTP.'
            })

        # OTP is correct
        request.session['reset_otp_verified'] = True

        return redirect('reset_password')

    return render(request, 'delivery/verify_reset_otp.html')


def admin_required(request):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return False

    return Customer.objects.filter(
        id=customer_id,
        is_admin=True
    ).exists()

def open_add_restaurant(request):

    if not admin_required(request):
        return redirect('open_signin')

    return render(request, 'delivery/add_restaurant.html')

def add_restaurant(request):

    if not admin_required(request):
        return redirect('open_signin')

    if request.method == 'POST':

        name = request.POST.get('name')
        picture = request.POST.get('picture')
        cuisine = request.POST.get('cuisine')
        rating = request.POST.get('rating')

        opening_time = request.POST.get('opening_time')
        closing_time = request.POST.get('closing_time')

        try:
            Restaurant.objects.get(name=name)

            return HttpResponse(
                "Restaurant already exists. Please choose a different name."
            )

        except Restaurant.DoesNotExist:

            Restaurant.objects.create(
                name=name,
                picture=picture,
                cuisine=cuisine,
                rating=rating,
                opening_time=opening_time,
                closing_time=closing_time,
            )

    return render(request, 'delivery/admin_home.html') 


def open_show_restaurants(request):

    if not admin_required(request):
        return redirect('open_signin')

    restaurantList = Restaurant.objects.all()

    current_time = datetime.now().time()

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', 'all')

    if search:
        restaurantList = restaurantList.filter(name__icontains=search)

    if status == 'active':
        restaurantList = restaurantList.filter(is_active=True)

    elif status == 'inactive':
        restaurantList = restaurantList.filter(is_active=False)

    # Check restaurant opening/closing time
    for restaurant in restaurantList:

        if restaurant.opening_time and restaurant.closing_time:

            if restaurant.opening_time <= current_time <= restaurant.closing_time:
                restaurant.schedule_status = "OPEN"
            else:
                restaurant.schedule_status = "CLOSED"

        else:
            restaurant.schedule_status = "TIME NOT SET"

    return render(request, 'delivery/show_restaurant.html', {

        'restaurantList': restaurantList,

        'search': search,

        'status': status

    })

def toggle_restaurant_status(request, restaurant_id):

    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)

    if restaurant.is_active:
        restaurant.is_active = False
    else:
        restaurant.is_active = True

    restaurant.save()

    return redirect('open_show_restaurants')

def open_update_restaurant(request, restaurant_id):

    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)

    return render(request, 'delivery/update_restaurant.html', {
        'restaurant': restaurant
    })
    

def update_restaurant(request, restaurant_id):

    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)

    if request.method == 'POST':

        restaurant.name = request.POST.get('name')
        restaurant.picture = request.POST.get('picture')
        restaurant.cuisine = request.POST.get('cuisine')
        restaurant.rating = request.POST.get('rating')

        restaurant.opening_time = request.POST.get('opening_time')
        restaurant.closing_time = request.POST.get('closing_time')

        restaurant.save()

        return redirect('open_show_restaurants')

    return render(
        request,
        'delivery/update_restaurant.html',
        {'restaurant': restaurant}
    )
def delete_restaurant(request, restaurant_id):

    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)
    restaurant.delete()

    return redirect('open_show_restaurants')

def open_update_menu(request, restaurant_id):

    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)
    itemList = restaurant.items.all()

    return render(request, 'delivery/update_menu.html', {
        'itemList': itemList,
        'restaurant': restaurant
    })
def update_menu(request, restaurant_id):

    # Admin-only protection
    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)
    error = None

    if request.method == 'POST':

        name = (request.POST.get('name') or '').strip()
        description = request.POST.get('description')
        price_raw = request.POST.get('price')
        vegetarian = request.POST.get('vegetarian') == 'on'
        category = request.POST.get('category') or 'other'
        available = request.POST.get('available') == 'on'
        picture = request.POST.get('picture')

        # Validate item name
        if not name:
            error = "Item name is required."

        elif len(name) > 50:
            error = "Item name must be 50 characters or fewer."

        # Validate price
        else:
            try:
                price = float(price_raw)

                if price <= 0:
                    raise ValueError

            except (TypeError, ValueError):
                error = "Price must be a positive number."

        # Check duplicate item
        if not error and Item.objects.filter(
            restaurant=restaurant,
            name__iexact=name
        ).exists():

            error = f'"{name}" is already on this menu. Choose a different name or edit the existing item.'

        # Create item if there is no error
        if not error:

            Item.objects.create(
                restaurant=restaurant,
                name=name,
                description=description,
                price=price,
                vegetarian=vegetarian,
                category=category,
                available=available,
                picture=picture,
            )

            return redirect(
                'open_update_menu',
                restaurant_id=restaurant.id
            )

    itemList = restaurant.items.all()

    return render(request, 'delivery/update_menu.html', {
        "itemList": itemList,
        "restaurant": restaurant,
        "error": error,
    })
    
def open_update_item(request, restaurant_id, item_id):

    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)
    item = Item.objects.get(id=item_id, restaurant=restaurant)

    return render(request, 'delivery/update_item.html', {
        'item': item,
        'restaurant': restaurant
    })

def update_item(request, restaurant_id, item_id):

    if not admin_required(request):
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)
    item = Item.objects.get(id=item_id, restaurant=restaurant)

    error = None
    
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        description = request.POST.get('description')
        price_raw = request.POST.get('price')
        vegetarian = request.POST.get('vegetarian') == 'on'
        category = request.POST.get('category') or 'other'
        available = request.POST.get('available') == 'on'
        picture = request.POST.get('picture')

        if not name:
            error = "Item name is required."
        elif len(name) > 50:
            error = "Item name must be 50 characters or fewer."
        else:
            try:
                price = float(price_raw)
                if price <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                error = "Price must be a positive number."

        if not error and Item.objects.filter(restaurant = restaurant, name__iexact = name).exclude(id = item.id).exists():
            error = f'"{name}" is already on this menu. Choose a different name.'

        if not error:
            item.name = name
            item.description = description
            item.price = price
            item.vegetarian = vegetarian
            item.category = category
            item.available = available
            item.picture = picture
            item.save()
            return redirect('open_update_menu', restaurant_id = restaurant.id)

    return render(request, 'delivery/update_item.html', {
        "item" : item,
        "restaurant" : restaurant,
        "error" : error,
    })

def delete_item(request, restaurant_id, item_id):

    if not admin_required(request):
        return redirect('open_signin')

    item = Item.objects.get(
        id=item_id,
        restaurant_id=restaurant_id
    )

    item.delete()

    return redirect(
        'open_update_menu',
        restaurant_id=restaurant_id
    )

    
def admin_home(request):

    if not admin_required(request):
        return redirect('open_signin')

    total_restaurants = Restaurant.objects.count()
    total_items = Item.objects.count()
    total_customers = Customer.objects.count()
    active_restaurants = Restaurant.objects.filter(is_active=True).count()
    inactive_restaurants = Restaurant.objects.filter(is_active=False).count()

    return render(request, 'delivery/admin_home.html', {
        'total_restaurants': total_restaurants,
        'total_items': total_items,
        'total_customers': total_customers,
        'active_restaurants': active_restaurants,
        'inactive_restaurants': inactive_restaurants,
    })
    
def view_menu(request, restaurant_id, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)
    itemList = restaurant.items.filter(available=True)

    categories = [
        ('starter', 'Starters'),
        ('main', 'Main Course'),
        ('dessert', 'Desserts'),
        ('beverage', 'Beverages'),
        ('other', 'Other'),
    ]

    category_data = []

    for key, label in categories:
        items = itemList.filter(category=key)

        if items.exists():
            category_data.append({
                'label': label,
                'items': items
            })

    return render(request, 'delivery/customer_menu.html', {
        'category_data': category_data,
        'restaurant': restaurant,
        'username': customer.username
    })
    
def add_to_cart(request, item_id, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    item = Item.objects.get(id=item_id)

    cart, created = Cart.objects.get_or_create(
        customer=customer
    )

    # Check whether the cart contains food
    # from a different restaurant.
    existing_item = CartItem.objects.filter(
        cart=cart
    ).select_related('item__restaurant').first()

    if existing_item:
        if existing_item.item.restaurant_id != item.restaurant_id:
            messages.warning(
                request,
                "Your cart contains food from another restaurant. "
                "Please clear your current cart before adding "
                "food from this restaurant."
            )

            return redirect(
                'show_cart',
                username=customer.username
            )

    # Add food from the same restaurant
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        item=item
    )

    MAX_QUANTITY = 20

    if not created:
        if cart_item.quantity < MAX_QUANTITY:
            cart_item.quantity += 1
            cart_item.save()
        else:
            messages.warning(
                request,
                "Maximum limit reached. "
                "You can add only 20 of this item."
            )
    else:
        cart_item.quantity = 1
        cart_item.save()

    cart.items.add(item)

    messages.success(request, f"{item.name} added to your cart!")

    return redirect(
    'view_menu',
    restaurant_id=item.restaurant.id,
    username=customer.username
)
    
def show_cart(request, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(id=customer_id).first()

    if not customer:
        return redirect('open_signin')

    username = customer.username

    try:
        cart = Cart.objects.get(customer=customer)

        # Make sure every item already in the cart
        # has a CartItem record
        for item in cart.items.all():
            CartItem.objects.get_or_create(
                cart=cart,
                item=item
            )

        cart_items = CartItem.objects.filter(
            cart=cart
        ).select_related('item')

        # Calculate total using quantity
        total = sum(
            cart_item.item.price * cart_item.quantity
            for cart_item in cart_items
        )

    except Cart.DoesNotExist:
        cart = None
        cart_items = []
        total = 0

    return render(request, 'delivery/cart.html', {
        'cart': cart,
        'cart_items': cart_items,
        'total': total,
        'username': username
    })
    
    
def increase_quantity(request, cart_item_id, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    cart_item = CartItem.objects.filter(
        id=cart_item_id,
        cart__customer_id=customer_id
    ).first()

    if not cart_item:
        return redirect('show_cart', username=request.session['username'])

    if cart_item.quantity < 20:
        cart_item.quantity += 1
        cart_item.save()
    else:
        messages.warning(
            request,
            "Maximum limit reached. You can add only 20 of this item."
        )

    return redirect('show_cart', username=request.session['username'])

def decrease_quantity(request, cart_item_id, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    cart_item = CartItem.objects.filter(
        id=cart_item_id,
        cart__customer_id=customer_id
    ).first()

    if not cart_item:
        return redirect('show_cart', username=request.session['username'])

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
    else:
        cart = cart_item.cart
        item = cart_item.item

        cart_item.delete()
        cart.items.remove(item)

    return redirect('show_cart', username=request.session['username'])

def remove_from_cart(request, cart_item_id, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    cart_item = CartItem.objects.filter(
        id=cart_item_id,
        cart__customer_id=customer_id
    ).first()

    if not cart_item:
        return redirect('show_cart', username=request.session['username'])

    cart = cart_item.cart
    item = cart_item.item

    cart_item.delete()
    cart.items.remove(item)

    return redirect('show_cart', username=request.session['username'])

def add_to_favorites(request, restaurant_id, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id, is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    restaurant = Restaurant.objects.get(id=restaurant_id)

    Favorite.objects.get_or_create(
        customer=customer,
        restaurant=restaurant
    )

    return redirect('customer_home', username=customer.username)


def remove_from_favorites(request, restaurant_id, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id, is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    Favorite.objects.filter(
        customer=customer,
        restaurant_id=restaurant_id
    ).delete()

    return redirect('customer_home', username=customer.username)
    
def show_favorites(request, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id, is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    favoriteList = Favorite.objects.filter(
        customer=customer
    ).select_related('restaurant')

    return render(request, 'delivery/favorites.html', {
        'favoriteList': favoriteList,
        'username': customer.username
    })
    
def profile(request, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    addressList = Address.objects.filter(customer=customer)

    return render(request, 'delivery/profile.html', {
        'customer': customer,
        'addressList': addressList,
        'username': customer.username
    })
    
def edit_profile(request, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        mobile = (request.POST.get('mobile') or '').strip()
        address = (request.POST.get('address') or '').strip()

        if Customer.objects.filter(
            email__iexact=email
        ).exclude(id=customer.id).exists():
            return render(request, 'delivery/edit_profile.html', {
                'customer': customer,
                'username': customer.username,
                'error': 'Email already registered.'
            })

        if Customer.objects.filter(
            mobile=mobile
        ).exclude(id=customer.id).exists():
            return render(request, 'delivery/edit_profile.html', {
                'customer': customer,
                'username': customer.username,
                'error': 'Mobile number already registered.'
            })

        customer.email = email
        customer.mobile = mobile
        customer.address = address
        customer.save()

        return redirect('profile', username=customer.username)

    return render(request, 'delivery/edit_profile.html', {
        'customer': customer,
        'username': customer.username
    })

def add_address(request, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    if request.method == 'POST':
        label = (request.POST.get('label') or '').strip()
        address = (request.POST.get('address') or '').strip()

        if label and address:
            Address.objects.create(
                customer=customer,
                label=label,
                address=address
            )

        return redirect('profile', username=customer.username)

    return render(request, 'delivery/add_address.html', {
        'customer': customer,
        'username': customer.username
    })
    
def edit_address(request, username, address_id):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    saved_address = Address.objects.filter(
        id=address_id,
        customer=customer
    ).first()

    if not saved_address:
        return redirect('profile', username=customer.username)

    if request.method == 'POST':
        label = (request.POST.get('label') or '').strip()
        address = (request.POST.get('address') or '').strip()

        if label and address:
            saved_address.label = label
            saved_address.address = address
            saved_address.save()

            return redirect('profile', username=customer.username)

    return render(request, 'delivery/edit_address.html', {
        'saved_address': saved_address,
        'customer': customer,
        'username': customer.username
    })
    
def delete_address(request, username, address_id):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    saved_address = Address.objects.filter(
        id=address_id,
        customer=customer
    ).first()

    if not saved_address:
        return redirect('profile', username=customer.username)

    if request.method == 'POST':
        saved_address.delete()

    return redirect('profile', username=customer.username)

def show_customers(request):
    # Allow only admins
    if not admin_required(request):
        return redirect('open_signin')

    # Get all registered customers
    customers = Customer.objects.all().order_by('-id')

    return render(request, 'delivery/show_customers.html', {
        'customers': customers,
        'total_customers': customers.count()
    })
    
def admin_orders(request):
    if not admin_required(request):
        return redirect('open_signin')

    orders = Order.objects.select_related(
        'customer',
        'restaurant'
    ).prefetch_related(
        'order_items'
    ).order_by('-created_at')

    return render(request, 'delivery/admin_orders.html', {
        'orders': orders
    })


@require_POST
def update_order_status(request, order_id):
    if not admin_required(request):
        return redirect('open_signin')

    order = get_object_or_404(
        Order,
        id=order_id
    )

    new_status = request.POST.get('status')

    valid_statuses = [
        'placed',
        'confirmed',
        'preparing',
        'out_for_delivery',
        'delivered',
        'cancelled',
    ]

    if new_status not in valid_statuses:
        messages.error(
            request,
            "Invalid order status."
        )
        return redirect('admin_orders')

    order.status = new_status
    order.save(update_fields=['status'])

    messages.success(
        request,
        f"Order #{order.id} status updated to "
        f"{order.get_status_display()}."
    )

    return redirect('admin_orders')

def checkout(request):

    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    # Get the customer's cart
    cart = Cart.objects.filter(customer=customer).first()

    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect(
            'show_cart',
            username=customer.username
        )

    cart_items = CartItem.objects.filter(
        cart=cart
    ).select_related('item')

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect(
            'show_cart',
            username=customer.username
        )

    # Calculate item subtotals
    for cart_item in cart_items:
        cart_item.subtotal = (
            cart_item.item.price * cart_item.quantity
        )

    # Calculate total
    total = sum(
        cart_item.subtotal
        for cart_item in cart_items
    )

    # Get the customer's saved addresses
    addresses = Address.objects.filter(
        customer=customer
    )

    # Process the selected address only on POST
    if request.method == 'POST':

        address_id = request.POST.get('delivery_address')

        selected_address = (
            addresses.filter(id=address_id).first()
            if address_id
            else None
        )

        if not selected_address:
            messages.error(
                request,
                "Please select a valid delivery address."
            )
            return redirect('checkout')

        # Save the address for the payment page
        request.session['checkout_address_id'] = selected_address.id

        return redirect('payment')

    # Display the Checkout page on GET
    return render(request, 'delivery/checkout.html', {
        'cart_items': cart_items,
        'total': total,
        'customer': customer,
        'username': customer.username,
        'addresses': addresses,
    })
    
def payment(request):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    # Check whether the customer selected a delivery address
    address_id = request.session.get('checkout_address_id')

    selected_address = Address.objects.filter(
        id=address_id,
        customer=customer
    ).first()

    if not selected_address:
        messages.warning(
            request,
            "Please select a delivery address first."
        )
        return redirect('checkout')

    cart = Cart.objects.filter(customer=customer).first()

    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect(
            'show_cart',
            username=customer.username
        )

    cart_items = CartItem.objects.filter(
        cart=cart
    ).select_related('item')

    if not cart_items.exists():
        messages.warning(request, "Your cart is empty.")
        return redirect(
            'show_cart',
            username=customer.username
        )

    # Calculate item subtotals
    for cart_item in cart_items:
        cart_item.subtotal = (
            cart_item.item.price * cart_item.quantity
        )

    # Calculate total
    total = sum(
        cart_item.subtotal
        for cart_item in cart_items
    )

    # Razorpay amount must be in paise
    razorpay_amount = int(
        Decimal(str(total)) * Decimal('100')
    )

    # Create Razorpay client
    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )

    # Create Razorpay order
    razorpay_order = client.order.create({
        'amount': razorpay_amount,
        'currency': 'INR',
        'payment_capture': 1
    })

    return render(request, 'delivery/payment.html', {
        'customer': customer,
        'selected_address': selected_address,
        'username': customer.username,
        'cart_items': cart_items,
        'total': total,

        # Razorpay information for payment.html
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_amount': razorpay_amount,
    })

@require_POST
def place_order(request):

    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    address_id = request.session.get('checkout_address_id')

    selected_address = Address.objects.filter(
        id=address_id,
        customer=customer
    ).first()

    if not selected_address:
        messages.error(
            request,
            "Please select a delivery address."
        )
        return redirect('checkout')

    payment_method = request.POST.get('payment_method')

    # --------------------------------------------------
    # COD PAYMENT
    # --------------------------------------------------

    if payment_method == 'COD':

        with transaction.atomic():

            cart = Cart.objects.select_for_update().filter(
                customer=customer
            ).first()

            if not cart:
                messages.error(
                    request,
                    "Your cart is empty."
                )
                return redirect(
                    'show_cart',
                    username=customer.username
                )

            cart_items = list(
                CartItem.objects.filter(
                    cart=cart
                ).select_related(
                    'item',
                    'item__restaurant'
                )
            )

            if not cart_items:
                messages.error(
                    request,
                    "Your cart is empty."
                )
                return redirect(
                    'show_cart',
                    username=customer.username
                )

            restaurant = cart_items[0].item.restaurant

            # Ensure all items belong to the same restaurant
            if any(
                cart_item.item.restaurant_id != restaurant.id
                for cart_item in cart_items
            ):
                messages.error(
                    request,
                    "Your cart contains items from different restaurants."
                )
                return redirect(
                    'show_cart',
                    username=customer.username
                )

            total = sum(
                (
                    Decimal(str(cart_item.item.price))
                    * cart_item.quantity
                    for cart_item in cart_items
                ),
                Decimal('0.00')
            )

            order = Order.objects.create(
                customer=customer,
                restaurant=restaurant,
                delivery_address=selected_address.address,
                payment_method='COD',
                total_amount=total,
                status='placed',
                payment_status='Pending'
            )

            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    item=cart_item.item,
                    item_name=cart_item.item.name,
                    quantity=cart_item.quantity,
                    price=Decimal(
                        str(cart_item.item.price)
                    )
                )
                for cart_item in cart_items
            ])

            # Clear cart
            CartItem.objects.filter(
                cart=cart
            ).delete()

            cart.items.clear()

        request.session.pop(
            'checkout_address_id',
            None
        )

        messages.success(
            request,
            f"Order #{order.id} placed successfully!"
        )

        return redirect(
            'order_confirmation',
            order_id=order.id
        )

    # --------------------------------------------------
    # RAZORPAY PAYMENT
    # --------------------------------------------------

    elif payment_method == 'RAZORPAY':

        razorpay_payment_id = request.POST.get(
            'razorpay_payment_id'
        )

        razorpay_order_id = request.POST.get(
            'razorpay_order_id'
        )

        razorpay_signature = request.POST.get(
            'razorpay_signature'
        )

        # Check whether Razorpay sent all required details
        if not all([
            razorpay_payment_id,
            razorpay_order_id,
            razorpay_signature
        ]):
            messages.error(
                request,
                "Razorpay payment information is missing."
            )
            return redirect('payment')

        # Create Razorpay client
        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            )
        )

        try:

            # Verify Razorpay payment signature
            client.utility.verify_payment_signature({
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            })

        except razorpay.errors.SignatureVerificationError:

            messages.error(
                request,
                "Razorpay payment verification failed."
            )
            return redirect('payment')

        # --------------------------------------------------
        # Signature verified successfully
        # Now create the actual CraveCart order
        # --------------------------------------------------

        with transaction.atomic():

            cart = Cart.objects.select_for_update().filter(
                customer=customer
            ).first()

            if not cart:
                messages.error(
                    request,
                    "Your cart is empty."
                )
                return redirect(
                    'show_cart',
                    username=customer.username
                )

            cart_items = list(
                CartItem.objects.filter(
                    cart=cart
                ).select_related(
                    'item',
                    'item__restaurant'
                )
            )

            if not cart_items:
                messages.error(
                    request,
                    "Your cart is empty."
                )
                return redirect(
                    'show_cart',
                    username=customer.username
                )

            restaurant = cart_items[0].item.restaurant

            # Ensure all items belong to the same restaurant
            if any(
                cart_item.item.restaurant_id != restaurant.id
                for cart_item in cart_items
            ):
                messages.error(
                    request,
                    "Your cart contains items from different restaurants."
                )
                return redirect(
                    'show_cart',
                    username=customer.username
                )

            total = sum(
                (
                    Decimal(str(cart_item.item.price))
                    * cart_item.quantity
                    for cart_item in cart_items
                ),
                Decimal('0.00')
            )

            order = Order.objects.create(
                customer=customer,
                restaurant=restaurant,
                delivery_address=selected_address.address,
                payment_method='RAZORPAY',
                total_amount=total,
                status='placed',
                payment_status='Paid',
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature
            )

            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    item=cart_item.item,
                    item_name=cart_item.item.name,
                    quantity=cart_item.quantity,
                    price=Decimal(
                        str(cart_item.item.price)
                    )
                )
                for cart_item in cart_items
            ])

            # Clear cart
            CartItem.objects.filter(
                cart=cart
            ).delete()

            cart.items.clear()

        request.session.pop(
            'checkout_address_id',
            None
        )

        messages.success(
            request,
            f"Payment successful! Order #{order.id} placed successfully!"
        )

        return redirect(
            'order_confirmation',
            order_id=order.id
        )

    # --------------------------------------------------
    # INVALID PAYMENT METHOD
    # --------------------------------------------------

    else:

        messages.error(
            request,
            "Please select a valid payment method."
        )

        return redirect('payment')
    
def order_confirmation(request, order_id):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    order = get_object_or_404(
        Order,
        id=order_id,
        customer_id=customer_id
    )

    return render(request, 'delivery/order_confirmation.html', {
        'order': order,
        'order_items': order.order_items.all(),
        'username': order.customer.username,
    })
    
def my_orders(request, username):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    orders = Order.objects.filter(
        customer=customer
    ).select_related(
        'restaurant'
    ).order_by('-created_at')

    return render(request, 'delivery/my_orders.html', {
        'orders': orders,
        'username': customer.username
    })
    
def order_tracking(request, order_id):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('open_signin')

    customer = Customer.objects.filter(
        id=customer_id,
        is_admin=False
    ).first()

    if not customer:
        return redirect('open_signin')

    order = get_object_or_404(
        Order,
        id=order_id,
        customer_id=customer_id
    )

    status_flow = [
        (
            'placed',
            'Order Placed',
            'Your order has been placed successfully.'
        ),
        (
            'confirmed',
            'Order Confirmed',
            'The restaurant has confirmed your order.'
        ),
        (
            'preparing',
            'Preparing',
            'Your food is being prepared.'
        ),
        (
            'out_for_delivery',
            'Out for Delivery',
            'Your order is on the way.'
        ),
        (
            'delivered',
            'Delivered',
            'Your order has been delivered.'
        ),
    ]

    current_index = -1

    for index, step in enumerate(status_flow):
        if step[0] == order.status:
            current_index = index
            break

    tracking_steps = []

    for index, step in enumerate(status_flow):

        if order.status == 'cancelled':
            step_class = 'cancelled-step'

        elif index < current_index:
            step_class = 'completed'

        elif index == current_index:
            step_class = 'current'

        else:
            step_class = 'upcoming'

        tracking_steps.append({
            'key': step[0],
            'title': step[1],
            'description': step[2],
            'class': step_class
        })

    return render(request, 'delivery/order_tracking.html', {
        'order': order,
        'tracking_steps': tracking_steps,
        'username': customer.username
    })


def logout(request):
    request.session.flush()
    return redirect('open_signin')