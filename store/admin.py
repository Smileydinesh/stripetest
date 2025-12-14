from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'price']  # Optional: Shows these fields in the list view
    list_filter = ['price']  # Optional: Adds filters