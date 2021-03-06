from django.shortcuts import render,redirect
from django.views.generic import View
from django.contrib import messages
from validate_email import validate_email
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode,urlsafe_base64_encode
from django.utils.encoding import force_text,force_bytes,DjangoUnicodeDecodeError
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from .util import generate_token
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib.auth import login,logout,authenticate

from django.contrib.auth.tokens import PasswordResetTokenGenerator
import threading

class EmailThread(threading.Thread):

    def __init__(self,email_message):
        self.email_message = email_message
        threading.Thread.__init__(self)

    def run(self):
        self.email_message.send()
        

class RegistrationView(View):
    def get(self,request):
        return render(request,'auth/register.html')

    def post(self,request):
        context = {
            'data' : request.POST,
            'has_error': False
        }
        # print(request.POST)

        email = request.POST.get('email')
        username = request.POST.get('username')
        fullname = request.POST.get('name')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')


        if not validate_email(email):
            messages.add_message(request,messages.ERROR,'Please provide a valid email')
            context['has_error'] = True

        if User.objects.filter(username=username).exists():
            messages.add_message(request,messages.ERROR,'Username is taken')
            context['has_error'] = True

        if len(password)<6:
            messages.add_message(request,messages.ERROR,'Password must be at least 6 characters long')
            context['has_error'] = True

        if password != password2:
            messages.add_message(request,messages.ERROR,'Passwords do not match!')
            context['has_error'] = True

        if User.objects.filter(email=email).exists():
            messages.add_message(request,messages.ERROR,'Email is taken')
            context['has_error'] = True

        if username == '':
            messages.add_message(request,messages.ERROR,'Username must be provided.')
            context['has_error'] = True
        
        if fullname == '':
            messages.add_message(request,messages.ERROR,'Fullname must be provided.')
            context['has_error'] = True



        if context['has_error']:
            return render(request,'auth/register.html',context,status=400)

        user = User.objects.create_user(username=username,email=email)
        user.set_password(password)
        user.first_name = fullname
        user.last_name = fullname
        user.is_active = False
        user.save()
        
        current_site = get_current_site(request)
        email_subject = 'Activate you account'
        message = render_to_string('auth/activate.html',
        {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': generate_token.make_token(user)
        }
        )

        email_message = EmailMessage(
            email_subject,
            message,
            settings.EMAIL_HOST_USER,
            [email],
        )

        EmailThread(email_message).start()


        messages.add_message(request,messages.SUCCESS,'Account created successfully')
        messages.add_message(request,messages.INFO,'Check your email to activate your account')



        return redirect('login')



class LoginView(View):
    def get(self,request):
        return render(request,'auth/login.html')

    def post(self,request):
        context = {
            'data': request.POST,
            'has_error':False
        }
        username = request.POST.get('username')
        password = request.POST.get('password')
        # print(username,password)
        if username == '':
            messages.add_message(request,messages.ERROR,'Username is required')
            context['has_error'] = True
            
        if password == '':
            messages.add_message(request,messages.ERROR,'Password is required')
            context['has_error'] = True

        user = authenticate(username=username,password=password)
        print(user)
        if not user and not context['has_error']:
            messages.add_message(request,messages.ERROR,'Invalid login')
            context['has_error'] = True
        
        if context['has_error']:
            return render(request,'auth/login.html',status=401,context=context)

        login(request,user)
        return redirect('home')


class ActivateAccountView(View):
    def get(self,request,uidb64,token):
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=uid)
        except Exception:
            user=None
        
        if user is not None and generate_token.check_token(user,token):
            user.is_active = True
            user.save()

            messages.add_message(request,messages.SUCCESS,'account activated successfully.')
            return redirect('login')
        return render(request,'auth/activate_failed.html',status=401)
            

class HomeView(View):
    def get(self,request):
        return render(request,'auth/home.html')

class LogoutView(View):
    def post(self,request):
        logout(request)
        messages.add_message(request,messages.SUCCESS,'Logout successfully')
        return redirect('login')

class RequestResetEmailView(View):
    def get(self,request):
        return render(request,'auth/request-reset-email.html')
        
    def post(self,request):
        email = request.POST['email']
        
        if not validate_email(email):
            messages.add_message(request,messages.ERROR,'Please enter a valid email')
            return render(request,'auth/request-reset-email.html')

        user = User.objects.filter(email=email)

        if user.exists():
            current_site = get_current_site(request)
            email_subject = 'Reset your password'
            message = render_to_string('auth/reset-user-password.html',
            {
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user[0].pk)),
                'token': PasswordResetTokenGenerator().make_token(user[0])
            }
            )

            email_message = EmailMessage(
                email_subject,
                message,
                settings.EMAIL_HOST_USER,
                [email],
            )

            EmailThread(email_message).start()

        messages.add_message(request,messages.SUCCESS,'We have sent you an email with instructions on how to reset it.')
        return render(request,'auth/request-reset-email.html')


class SetNewPasswordView(View):
    def get(self,request,uidb64,token):
        context={
            'uidb64':uidb64,
            'token':token
        }
        try:
            user_id = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=user_id)

            if not PasswordResetTokenGenerator().check_token(user,token):
                messages.info(request,'Password reset link is invalid,please request a new one')
                return render(request,'auth/request-reset-email.html')
        except DjangoUnicodeDecodeError as exp:
            messages.add_message(request,messages.ERROR,'Something went wrong')
            return render(request,'auth/set-new-password.html',context)

        return render(request,'auth/set-new-password.html',context)
        
    def post(self,request,uidb64,token):
        context={
            'uidb64':uidb64,
            'token':token,
            'has_error':False
        }
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        if len(password)<6:
            messages.add_message(request,messages.ERROR,'Password must be at least 6 characters long')
            context['has_error'] = True

        if password != password2:
            messages.add_message(request,messages.ERROR,'Passwords do not match!')
            context['has_error'] = True

        if context['has_error']:
            return render(request,'auth/set-new-password.html',context)    
        try:
            user_id = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=user_id)
            user.set_password(password)
            user.save()
            messages.add_message(request,messages.SUCCESS,'Password Reset successfully, you can now login with new password')
            return redirect('login')
        except DjangoUnicodeDecodeError as exp:
            messages.add_message(request,messages.ERROR,'Something went wrong')
            return render(request,'auth/set-new-password.html',context)

        return render(request,'auth/set-new-password.html',context)