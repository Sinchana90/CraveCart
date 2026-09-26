
from django.db import models

# Create your models here.
class Customer(models.Model):
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=128)
    email = models.CharField(max_length=50, unique=True)
    mobile = models.CharField(max_length=12, unique=True)
    address = models.CharField(max_length=100, blank=True, default='')
    
    is_admin = models.BooleanField(default=False)
    
    
class Restaurant(models.Model):
    name = models.CharField(max_length=50)
    picture = models.URLField(max_length=200, default='https://img.freepik.com/premium-vector/restaurant-logo-design-template_79169-56.jpg?w=2000')
    cuisine = models.CharField(max_length=200)
    rating = models.FloatField()
    
    is_active = models.BooleanField(default=True)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    
class Favorite(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="favorites"
    )

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="favorited_by"
    )

    class Meta:
        unique_together = ('customer', 'restaurant')
    
class Item(models.Model):
    CATEGORY_CHOICES = [
        ('starter', 'Starter'),
        ('main', 'Main Course'),
        ('dessert', 'Dessert'),
        ('beverage', 'Beverage'),
        ('other', 'Other'),
    ]

    restaurant = models.ForeignKey(Restaurant, on_delete = models.CASCADE, related_name = "items")
    name = models.CharField(max_length = 50)
    description = models.CharField(max_length = 200)
    price = models.FloatField()
    vegetarian = models.BooleanField(default=False)
    category = models.CharField(max_length = 20, choices = CATEGORY_CHOICES, default = 'other')
    available = models.BooleanField(default=True)
    picture = models.URLField(max_length = 400, default='https://www.indiafilings.com/learn/wp-content/uploads/2024/08/How-to-Start-Food-Business.jpg')

    class Meta:
        unique_together = ('restaurant', 'name')
        
class Cart(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="cart"
    )

    items = models.ManyToManyField(
        "Item",
        related_name="carts"
    )

    def total_price(self):
        return sum(item.price for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'item')

    def total_price(self):
        return self.item.price * self.quantity
    
class Address(models.Model):
    ADDRESS_TYPES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='addresses'
    )

    label = models.CharField(
        max_length=20,
        choices=ADDRESS_TYPES,
        default='other'
    )

    address = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.customer.username} - {self.label}"
    
    
class Order(models.Model):

    STATUS_CHOICES = [
        ('placed', 'Placed'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_CHOICES = [
        ('COD', 'Cash on Delivery'),
        ('RAZORPAY', 'Online Payment'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='orders'
    )

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.PROTECT,
        related_name='orders'
    )

    delivery_address = models.CharField(max_length=200)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default='COD'
    )

    razorpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    razorpay_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    razorpay_signature = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    payment_status = models.CharField(
       max_length=20,
      default='Pending'
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='placed'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.customer.username}"


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='order_items'
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT
    )

    item_name = models.CharField(max_length=50)

    quantity = models.PositiveIntegerField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def total_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.item_name} × {self.quantity}"