from .models import Wallet, Crypto, Amount
from .forms import WalletForm, CryptoForm
from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from decouple import config
from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
from django.core.exceptions import ObjectDoesNotExist
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin


url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest'
api_key = config('api_key')

headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': api_key,
}

# Create your views here.

@login_required
def home(request):
    return render(request, 'home.html')

def signup(request):
    error_message = ''
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
        else:
            error_message = 'invalid signup - please try again'
    form = UserCreationForm()
    context = {
        'form': form,
        'error': error_message,
    }
    return render(request, 'registration/signup.html', context)

@login_required
def wallets_index(request):
    # get all wallets
    wallets = Wallet.objects.filter(user = request.user)
    symbols_arr = []
    wallets_arr = []
    for wallet in wallets:
        coins_arr = []
        wallet_coins = Amount.objects.filter(wallet=wallet.id)
        for coin in wallet_coins:
            if (coin.crypto.symbol not in symbols_arr):
                symbols_arr.append(coin.crypto.symbol)
            coin_object = {
                'symbol': coin.crypto.symbol,
                'amount': coin.amount,
            }
            coins_arr.append(coin_object)
        wallet_obj = {
            'id': wallet.id,
            'name': wallet.name,
            'crypto': coins_arr,
        }
        # add coins_not_in_wallet to each wallet
        wallet_obj['crypto_not_in_wallet'] =  Crypto.objects.exclude(id__in=wallet_coins.values_list('crypto'))
        wallets_arr.append(wallet_obj)
    # get all symbols in all wallets
    symbols = ','.join(symbols_arr)
    parameters = {
        'symbol': symbols
    }
    session = Session()
    session.headers.update(headers)
    try:
        # api call for all coins in all wallets
        response = session.get(url, params=parameters)
        data = json.loads(response.text)
        data = data['data']
        coins = []
        for symbol in symbols_arr:
            coin_obj = data[symbol][0]
            obj = {
                'symbol': symbol,
                'name': coin_obj['name'],
                'last_updated': coin_obj['last_updated'],
                'quote': coin_obj['quote']['USD'],
            }
            coins.append(obj)
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)
    
    for wallet in wallets_arr:
        for coin in wallet['crypto']:
            for obj in coins:
                if obj['symbol'] == coin['symbol']:
                    coin['price'] = obj['quote']['price']
                    coin['name'] = obj['name']
    print(f"wallets array: {wallets_arr}")
    wallet_form = WalletForm()
    return render(request, 'dashboard.html', {
        'wallets': wallets_arr,
        'wallet_form': wallet_form,
    })

@login_required
def add_wallet(request):
    form = WalletForm(request.POST)
    if form.is_valid():
        new_wallet = form.save(commit=False)
        new_wallet.user = request.user
        new_wallet.save()
    return redirect('dashboard')

@login_required
def wallets_detail(request, wallet_id):
    wallet = Wallet.objects.get(id=wallet_id)
    wallet_coins = Amount.objects.filter(wallet=wallet.id)
    coins_not_in_wallet = Crypto.objects.exclude(id__in=wallet_coins.values_list('crypto'))
    wallet_obj = {
        'id': wallet.id,
        'name': wallet.name,
        'crypto': wallet_coins,
    }
    return render(request, 'wallets/detail.html', { 
        'wallet': wallet_obj, 
        'avail_crypto': coins_not_in_wallet 
    })

def crypto_lookup(request):
    form = CryptoForm(request.POST)
    if form.is_valid():
        symbol = form.cleaned_data['symbol']
        try:
            # prevents user from adding duplicate coins
            database_crypto = Crypto.objects.get(symbol=symbol)
            return redirect('crypto_list')  
        except ObjectDoesNotExist:
            print("Symbol not found on database")
        parameters = {
            'symbol': symbol
        }
        session = Session()
        session.headers.update(headers)
        try:
            response = session.get(url, params=parameters)
            if(response):
                data = json.loads(response.text)
                data = data['data']
                crypto = data[symbol][0]
                print(crypto)
                return render(request, 'crypto/confirm.html', {
                    'name': crypto['name'],
                    'symbol': crypto['symbol'],
                    'coin_market_cap_id': crypto['id'],
                })
            return redirect('crypto_list')
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            print(e)

def add_crypto(request, coin_market_cap_id, symbol):
    Crypto.objects.create(symbol=symbol)
    return redirect('crypto_list')

class CryptoList(ListView):
    model = Crypto

    def get_context_data(self, **kwargs):
        context = super(CryptoList, self).get_context_data(**kwargs)
        context['form'] = CryptoForm()
        return context