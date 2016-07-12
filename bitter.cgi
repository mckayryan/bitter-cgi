#!/usr/bin/perl -w

# written by 4ryanmckay2@gmail.com 09/15
# for (UNSW) COMP2041/9041 assignment 2
# http://cgi.cse.unsw.edu.au/~cs2041/assignments/bitter/
use diagnostics;
use Data::Dumper qw(Dumper);
use CGI qw/:all/;
use CGI::Carp qw/fatalsToBrowser warningsToBrowser/;


sub main() {
    # print start of HTML ASAP to assist debugging if there is an error in the script
    print page_header();

    # Now tell CGI::Carp to embed any warning in HTML
    warningsToBrowser(1);

    # define some global variables
    $DEBUG = 0;
    $dataset_size = "medium";
    $users_dir = "dataset-$dataset_size/users";
    our %USER_DATA;
    our %USER_BLEATS;
    our %USER_INDEX;
    our %BLEAT_DATA;
    our %MENTIONS;
    # Determines if supplied data by user is valid
    # If yes, calls main control loop
    verify_user();

}

#############
# Front End #
#############

# This function is the main control once a user has logged in and
# is authenticated. All front end pages are served via this function
sub control_loop
{
    my ($authenticated, $user, $Users) = @_;
    # display information functions
    # main control loop
    if ($authenticated) {
        # Displaying specific user pages, profiles (random) or moving
        # between profiles
        if (param('profiles') || param('next_user') || param('user_page')) {
            print page_navbar();
            # process bleat details after navbar loads
            process_bleats();
            process_user_bleats($Users);
            print user_profiles($Users);
        # Searching for users or bleats
        } elsif (param('search')) {
            print page_navbar();
            # process bleat details after navbar loads
            process_bleats();
            process_user_bleats($Users);
            print search_users();
        # Create a new bleat
        } elsif (param('bleat_page')) {
            print page_navbar();
            # process bleat details after navbar loads
            process_bleats();
            process_user_bleats($Users);
            print bleat_html();
        # Update database with new bleat details
        } elsif (param('submit_bleat')) {
            print page_navbar();
            # process bleat details after navbar loads
            process_bleats();
            process_user_bleats($Users);
            process_new_bleat();
            print user_home_page($user);
        # Logged in user home page
        } else {
            print page_navbar();
            # process bleat details after navbar loads
            process_bleats();
            process_user_bleats($Users);
            print user_home_page($user);
        }
    } else {
        verify_user();
    }
    print page_trailer();
}

#
# using passed hidden variables, this function verifies user username
# and passwords and maintains a users loggin status until the page is reloaded
sub verify_user
{
    $username = param('username') || '';
    $password = param('password') || '';
    $authenticated = param('authenticated') || '';
    # protection from injection attacks
    prevent_XSS(\$username);             prevent_XSS(\$password);
    $username = format_line($username);  $password = format_line($password);
    $mode = '';
    # move to logout first as requires no verification
    if (param('logout')) {
        print logout_html();
    # has been authenticated previously
    } elsif ($authenticated) {
        @users = sort(glob("$users_dir/*"));
        process_users(\@users);
        control_loop($authenticated, $username, \@users);
    # Username && password must exist to authenticate
    } elsif ($username && $password) {
        # process all user related data in order to verify
        @users = sort(glob("$users_dir/*"));
        process_users(\@users);
        # user must exist
        if (exists($USER_DATA{$username})) {
            # supplied pass matches recorded
            if ($password eq $USER_DATA{$username}{'password'}) {
                $authenticated = 1;
                control_loop($authenticated, $username, \@users);
            } else {
                # password was incorrect
                $mode = 'invalid pass';
                print login_html($mode, $username, $password);
            }
        # username does not exist
        } else {
            $mode = 'invalid user';
            print login_html($mode, $username, $password);
        }
    # User did not input a field
    } elsif ((!$username && $password) || ($username && !$password)) {
        $mode = 'invalid input';
        print login_html($mode, $username, $password);
    # intial page
    } else {
        $mode = 'initial';
        print login_html($mode, $username, $password);
    }
}

#
# This function takes user input, filters it and uses regex to find
# username, user full names and bleat that contain that substring.
# It calls a HTML function that outputs that information
sub search_users
{
    $search_input = param('search');
    $username = param('username');
    # formatt user input to prevent security breaches
    prevent_XSS(\$search_input);
    $search_input = format_line($search_input);
    # search users for matches
    foreach my $user (keys %USER_DATA) {
        push @user_matches, $user if ($user =~ /$search_input/);
        # check for match with full name
        if ($USER_DATA{$user}{'full_name'} =~ /$search_input/) {
            push @user_matches, $user;
        }
    }
    # search bleats for matches
    foreach $key (keys %BLEAT_DATA) {
        if ($BLEAT_DATA{$key}{'bleat'} &&
           ($BLEAT_DATA{$key}{'bleat'} =~ /$search_input/)) {
            push @bleat_matches, $key;
        }
    }
    # load matches into hash with formating/HMTL form for output
    foreach $user (@user_matches) {
        $user_name = "$USER_DATA{$user}{'full_name'}";
        $button_form = get_link($user, $user, ($USER_INDEX{$user}+1), "user_page");

        if (!exists($u_matches{$user})) {
            $u_matches{$user}{'username'} = $button_form;
            $u_matches{$user}{'full_name'} = $user_name;
        }
    }
    # load all matches and formatting into single scalar
    foreach my $match (keys %u_matches) {
        $matched_usernames .= "$u_matches{$match}{'username'} - ";
        $matched_usernames .= "$u_matches{$match}{'full_name'}<br>";
    }
    # load hash to be sorted by time, user information is also required
    foreach my $key (@bleat_matches) {
        my $time = $BLEAT_DATA{$key}{'time'};
        my $author = $BLEAT_DATA{$key}{'username'};
        if (!exists($b_matches{$time}{$author})) {
            $b_matches{$time}{$author} = $BLEAT_DATA{$key}{'bleat'};
        }
    }
    $matched_bleats = format_bleats(\%b_matches);
    return search_html($matched_usernames, $matched_bleats);
}


# This fucntion organises and displays the users home page once they have
# logged in and been authenticated. It displays all Bleats related to the
# user: bleats they posted, bleats they have been tagged in & bleats from
# those they follow (in reverse chronological order)
sub user_home_page
{
    my ($user) = @_;
    $user = extract_username($user);
    # gather users bleats
    get_user_bleats(\%home_bleats, $user);
    # gather bleats from users that user follows
    foreach my $listens (keys %{ $USER_DATA{$user}{'listens'} }) {
      push @user_listens, $listens;
    }
    foreach $listens (@user_listens) {
      get_user_bleats(\%home_bleats, $listens);
    }
    # gather bleats that mention user
    get_mentioned_bleats(\%home_bleats, $user);
    # add html formating and sort in reverse chronological order
    my $home_bleats = format_bleats(\%home_bleats);
    print user_page_html(\$home_bleats);

}


# Show unformated details for user "n".
# This function is used to display specific user pages (via button links)
# or scroll through user profiles
# It calls a HTML function to display the user information
sub user_profiles
{
    my @users = @{$_[0]};
    my $n = param('n') || '0';
    # user_page was offset by 1 to trigger param when $n = 0
    $n = param('user_page') - 1 if (param('user_page'));
    $n = 0 if (param('profiles'));
    # control which user is displayed (cycles)
    my $user_to_show  = $users[$n % @users];
    get_user_data(\%to_print, $user_to_show);
    # move to next user
    my $next_user = $n + 1;
    return user_profiles_html(\%to_print, $next_user);
}

##################
# HTML Functions #
##################

#
# Displays the login page and produces errors when user supplies inadequate
# or incorrect information (username / password)
sub login_html
{
    my ($mode, $user, $pass) = @_;
    # Message to user above login
    # Includes HTML formating as error message differs to welcome message in style
    $header = "<h2><strong>Welcome to Bitter.</h2>";
    $message1 = "<h4 class=\"text-danger\"><strong>";
    if ($mode =~ /invalid input/) {
        $message1 .= "Do, or do not... there is no try.";
    } elsif ($mode =~ /invalid user/) {
        $message1 .= "Thats not the username you're looking for...";
    } elsif ($mode =~ /invalid pass/) {
        $message1 .= "That's not the password you're looking for...";
    } else {
        $message1 = "<h4>Connect with your friends... and other Bitter people.";
    }
    $message1 .= "</strong></h4>";

    return <<eof

<body class="image-login">
<!-- backgroung image modified from:
http://www.hdwallpapers.in/windows_xp_bliss-wallpapers.html -->
<br><br><br><br>
<div class="container">
  <div class="jumbotron jumbo-pad">
    <ul><div class="container">$header$message1<br></div>
      <div class="container">
        <form class="form-inline" method="post" action="" enctype="multipart/form-data">
          <div class="form-group">
            <label class="sr-only" for="exampleInputEmail3">Username</label>
            <input type="text" name="username" class="form-control" id="exampleInputEmail3" placeholder="Username">
          </div>
          <div class="form-group">
            <label class="sr-only" for="exampleInputPassword3">Password</label>
            <input type="text" name="password" class="form-control" id="exampleInputPassword3" placeholder="Password">
          </div>
          <input type="submit" value="Login" class="btn btn-success">
        </form>
      </div>
    </ul>
  </div>
</div>
</body>
eof
}

#
# Displays the log  out page with a link back to the login page
sub logout_html
{
    my $user = param('username');
    my $message1 = "$user we are sorry to see you get some sunshine back into your life!";
    my $message2 = "Drop by if you are ever feeling Bitter...";
    my $message3 = "... how about now?";
    my $btn1 = "Ok... I'm Bitter!!!";
    return <<eof
<body class="image-logout">
<!-- Image suppied by:
http://www.public-domain-image.com/free-images/flora-plants/flowers/sunflowers-pictures/sunflowers-helianthus-annuus.jpg -->
<br><br><br><br><br>
<div class="container">
  <div class="jumbotron">
    <ul>
      <h3 class="text-success"><strong>$message1</strong></h3><br>
      <p class="text-success">$message2</p>

  </div>
</div>
<br><br><br><br><br><br><br>
<div class="container">
  <div class="jumbotron">

      <h4 class="text-success">$message3</h4>
      <form method="POST" action="">
        <button type="submit" class="btn btn-success btn-lg">$btn1</button>
      </form>
    </ul>
  </div>
</div>
</body>
eof

}

#
# Displays the results of a user search including:
# Username, User's full name and bleat matches
sub search_html
{
    my ($user_result, $bleat_result) = @_;
    my $username = param('username');
    my $message1 = "Are these the bitter melons you were looking for?";
    my $heading1 = "Here are the bitter melons that match your search...";
    $sub_head1 = '';
    if ($user_result) {
			  my $sub_head1 = "Username - Full name";
	  } else {
	  		$user_result = "Oops... no bitter melons were found.";
    }
    my $heading2 = "Here are the bitter bleats that match your search...";
        if (!$bleat_result) {
      	$bleat_result = "Oops... no bitter bleats were found.";
    }
    return <<eof
<body class="image-main-user">
<!-- background image modified from:
http://www.collective-evolution.com/2014/12/07/research-shows-this-one-plant-can-kill-cancer-cells-treat-diabetes/ -->
<br>
<div class="container">
  <div class="row">
  <div class="col-md-offset-1 col-md-10 col-xs-12">
    <div class="panel panel-success">
      <div class="panel-heading"><strong class="text-success">$heading1</strong></div>
      <div class="panel-body">
        <div class="row">
          <div class="col-lg-8 col-md-8 col-sm-8 col-xs-8">
             <ul><h5 class="text-success"><strong>$sub_head1</strong></h5>
               <p>$user_result</p>
             </ul>
          </div>

        </div>
      </div>
    </div>
  </div>
  </div>
  <div class="row">
  <div class="col-md-offset-1 col-md-10 col-xs-12">
    <div class="panel panel-success">
      <div class="panel-heading"><strong class="text-success">$heading2</strong></div>
      <div class="panel-body text-indent">$bleat_result</div>
    </div>
  </div>
  </div>
</div>
</body>
eof
}

#
# Displays the page in which users create bleats and takes raw input and
# passes that to be processed as a new bleat
sub bleat_html
{
    my $username = param('username');
    my $heading1 = "Bitter??? Bleat about it!";
    my $body2 = "Before you get Bitter, remember...";
    my $body3 = "You have to get all of your Bitterness out in 142 characters";
    my $body4 = "The @ symbol before another Bitter user's name will tag them as mentioned in your bleat";
    my $body5 = "A # before any word denotes a key word and will link your bleat with other Bitter souls";
    my $body6 = "Strictly no positivity or sweetness of any kind... That is not a suggestion!";
    my $button1 = "Bleat It!";
    return <<eof
<body class="image-main">
<!-- background image modified from:
http://www.collective-evolution.com/2014/12/07/research-shows-this-one-plant-can-kill-cancer-cells-treat-diabetes/ -->
<br><br><br><br>
<div class="container">
  <div class="row">
  <div class="col-md-offset-1 col-md-10 col-xs-12">
    <div class="panel panel-success">
      <div class="panel-heading"><h5><strong class="text-success">$heading1</strong></h5></div>
      <div class="panel-body">
        <ul class="text-indent"><strong class="text-success">$body2</strong><br>
          <li class="text-indent">$body3<br>
            <li class="text-indent">$body4<br>
            <li class="text-indent">$body5<br>
            <li class="text-indent">$body6
          </li><br>
          <form method="POST" action="">
            <input type="hidden" name="username" value="$username">
            <input type="hidden" name="authenticated" value="1">
            <input type="textarea" class="form-control" name="bleat" placeholder="Tell us all what you're Bitter about..." maxlength="142"><br>
            <button type="submit" class="btn btn-success btn-lg pull-right" name="submit_bleat" value="1">$button1</button>
          </form>
          </ul>
      </div>
    </div>
  </div>
  </div>
</div>
</body>
eof
}

#
# This page displays specified user profile, or scrolls through all users
# profiles. This page is also used when a user button/ link is clicked
sub user_profiles_html
{
    my ($Print, $next_user) = @_;
    # All Displayed data
    my $btn_message = "Next!";
    my $profile_image = "/$$Print{'image'}";
    my $heading1 = $$Print{'username'};
    my $heading2 = "Stalking Information";
    my $heading3 = "$$Print{'username'} Bleats";
    my $body1 = "Full Name:<br><br>Suburb:<br><br>Coordinates:<br><br>Listens to:</strong>";
    my $body2 = "$$Print{'full_name'}<br><br>$$Print{'suburb'}<br><br>$$Print{'coordinates'}";
    my $body3 = $$Print{'bleats'};
    my ($listens1, $listens2) = split /&\|\!/,$$Print{'listen_to'},2;
    # collect params for passing as hidden variables so that user stays
    # logged in
    my $username = param('username');
    return <<eof
<body class="image-main-user">
<!-- background image modified from:
http://www.collective-evolution.com/2014/12/07/research-shows-this-one-plant-can-kill-cancer-cells-treat-diabetes/ -->
<br>
<div class="container">
  <div class="row">
    <div class="col-md-offset-1 col-md-3 col-sm-4 col-xs-4">
      <div class="panel panel-success">
        <div class="panel-heading"><strong class="text-success">$heading1</strong></div>
        <div class="panel-body">
          <!-- no_image.jpg modified from: http://lifehacker.com/5984918/nine-practices-to-help-you-say-no-without-feeling-like-a-jerk -->
          <img src="$profile_image" class="img-responsive" alt="Responsive image">
          <br>
      </div>
      </div>
    </div>
    <div class=" col-md-offset-1 col-md-6 col-sm-8 col-xs-8">
      <div class="panel panel-success">
        <div class="panel-heading">
          <strong class="text-success">$heading2</strong>
        </div>
        <div class="panel-body">
            <div class="row">
              <div class="col-lg-6 col-md-6 col-sm-6 col-xs-6">
                <h5><strong>$body1</h5>
                <div class="row">
                  <div class="col-lg-6 col-md-6 col-sm-6 col-xs-6">
                      $listens1
                  </div>
                  <div class="col-lg-6 col-md-6 col-sm-6 col-xs-6">
                      $listens2
                  </div>
                </div>
              </div>
              <div class="col-lg-6 col-md-6 col-sm-6 col-xs-6">
                <h5>$body2</h5><br><br><br>
                <form method="POST" action="">
                  <input type="hidden" name="n" value="$next_user">
                  <input type="hidden" name="username" value="$username">
                  <input type="hidden" name="authenticated" value="1">
                  <button type="submit" class="btn btn-success btn-lg pull-right" name="next_user" value="1">$btn_message</button>
                </form>
              </div>
            </div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="container">
  <div class="row">
  <div class="col-md-offset-1 col-md-10 col-sm-12 col-xs-12">
    <div class="panel panel-success">
      <div class="panel-heading"><strong class="text-success">$heading3</strong></div>
      <div class="panel-body">
        $body3
        <form method="POST" action="">
          <input type="hidden" name="n" value="$next_user">
          <input type="hidden" name="username" value="$username">
          <input type="hidden" name="authenticated" value="1">
          <button type="submit" class="btn btn-success btn-lg pull-right" name="next_user" value="1">$btn_message</button><br>
        </form>
      </div>
    </div>
  </div>
</div>
<p>
</body>
eof
}
#
# Displays logged in user's home page
# This may be on log in, or after making a bleat
sub user_page_html
{
    my ($Bleats) = @_;
    my $user = param('username');
    my $message1 = "Hi $user!";
    my $message2 = "Here are all of the Bleats from the Bitter people that you care about, and that care about your Bitter self.";
    my $message3 = "Feeling Bitter?";
    if (param('submit_bleat')) {
        $message2 = "You sure showed the Bitterverse how Bitter you can be!!!";
        $message3 = "Still Feeling Bitter???";
    }
    my $bleats_heading = "Ahhh so much Bitterness...";

    my $btn_message1 = "Bleat it!";

    return <<eof
<body class="image-main-user">
<!-- background image modified from:
http://www.collective-evolution.com/2014/12/07/research-shows-this-one-plant-can-kill-cancer-cells-treat-diabetes/ -->
<br>
<div class="container">
  <div class="row">
  <div class="col-md-offset-1 col-md-10 col-xs-12">
    <div class="jumbotron">
      <h3 class="text-success"><strong>$message1</strong></h3>
      <p>$message2</p>
      <form method="POST" action="">
        <input type="hidden" name="authenticated" value="1">
        <input type="hidden" name="username" value="$user">
        <button type="submit" class="btn btn-success btn-lg pull-right" name="bleat_page" value="1">$btn_message1</button><br><br>
      </form>
    </div>
  </div>
  </div>
</div>
<div class="container">
  <div class="row">
  <div class="col-md-offset-1 col-md-10 col-xs-12">
    <div class="panel panel-success">
      <div class="panel-heading"><h3><strong class="text-indent">$bleats_heading</strong></h3></div>
      <div class="panel-body text-indent">$$Bleats</div>
    </div>
  </div>
  </div>
</div>
</body>
eof
}

#
# HTML placed at the top of every page
#
sub page_header {
    return <<eof
Content-Type: text/html

<!DOCTYPE html>
<html lang="en">
<head>
<title>Bitter</title>
    <!-- Latest compiled and minified CSS -->
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">

    <!-- My CSS including modified Bootstrap -->
    <link href="bitter.css" type="text/css"  rel="stylesheet">
    <!-- Google fonts CSS -->
    <link href="http://fonts.googleapis.com/css?family=Lekton" rel="stylesheet" type="text/css">
    <link href="http://fonts.googleapis.com/css?family=Molengo" rel="stylesheet" type="text/css">

</head>
eof
}

# HTML for navbar that is present on all pages bar login/ logout
sub page_navbar
{
   $user = param('username');
   my $nav_btn1 = "My Bitter";
   my $nav_btn2 = "Profiles";
   my $nav_btn3 = "GO!";
   my $nav_btn4 = "Logout";
   my $nav_btn5 = "Bleat It!";
   my $placeholder = "Find a Bitter Soul";

return <<eof
<div class="container">
  <div class="row">
  <div class="col-md-offset-1 col-md-10 col-xs-12">
  <nav class="navbar navbar-theme">
    <div class="navbar-header">

      <form method="POST" action="">
        <input type="hidden" name="username" value="$user">
        <input type="hidden" name="authenticated" value="1">
        <button type="submit" class="btn btn-success ghost-btn btn-lg nav-btn-lpad" name="user_home">$nav_btn1</button>
      </form>
    </div>
      <form method="POST" action="">
        <ul class="nav navbar-nav">
          <input type="hidden" name="username" value="$user">
          <input type="hidden" name="authenticated" value="1">
          <button type="submit" class="btn btn-success ghost-btn btn-lg nav-btn-lpad" name="profiles" value="1">$nav_btn2</button>
        </ul>
      </form>
      <form method="POST" action="">
        <ul class="nav navbar-nav">
          <input type="hidden" name="username" value="$user">
          <input type="hidden" name="authenticated" value="1">
          <button type="submit" class="btn btn-success ghost-btn btn-lg nav-btn-lpad" name="bleat_page" value="1">$nav_btn5</button>
        </ul>
      </form>
      <form class="navbar-form navbar-nav navbar nav-search-pad" method="post" action="" role="search">
        <div class="form-group">
          <input type="text" name="search" class="form-control" placeholder="$placeholder">
          <input type="hidden" name="username" value="$user">
          <input type="hidden" name="authenticated" value="1">
        </div>
        <input type="submit" class="btn btn-success ghost-btn" value="$nav_btn3">
      </form>
      <ul class="nav navbar-nav navbar-right" role="navigation">
        <form method="POST" action="">
          <input type="hidden" name="username" value="$user">
          <button type="submit" class="btn btn-success ghost-btn nav-btn-rpad" name="logout" value="1">$nav_btn4</button>
        </form>
      </ul>
    </div><!-- /.navbar-collapse -->
  </div>
  </div>
</nav>
</div><!-- /.container-fluid -->
eof
}


#
# HTML placed at the bottom of every page
# It includes all supplied parameter values as a HTML comment
# if global variable $debug is set
#
sub page_trailer {
    print "<link rel=\"stylesheet\" href=\"//netdna.bootstrapcdn.com/bootstrap/3.3.2/js/bootstrap.min.js\">";
    my $html = "";
    $html .= join("", map("<!-- $_=".param($_)." -->\n", param())) if $DEBUG;
    $html .= end_html;
    return $html;
}

####################
#  Get Functions   #
####################

# Gather time, user and raw bleat data for a specified user
sub get_user_bleats
{
    my ($Bleats, $user) = @_;
    foreach $b_key (keys %{ $USER_BLEATS{$user} }) {
        $b_time = $BLEAT_DATA{$b_key}{'time'};
        if (!($$Bleats{$b_time}{$user} = $BLEAT_DATA{$b_key}{'bleat'})) {
            print "<!-- $0: bleat and time could not be loaded --><br>";
        }
    }
}

# Gathers all bleats in which a specified user is mentioned
sub get_mentioned_bleats
{
    my ($men_bleats, $user) = @_;
    # Compare all mentioned users to specified user
    foreach $key (keys %MENTIONS) {
        foreach $men_user (keys %{ $MENTIONS{$key} }) {
            if ($men_user =~ $user) {
                # add in time and user information for sorting and displaying
                my $time = $BLEAT_DATA{$key}{'time'};
                my $author = $BLEAT_DATA{$key}{'username'};
                # load raw bleat as value
                if (!($$men_bleats{$time}{$author} = $BLEAT_DATA{$key}{'bleat'})) {
                    print "<!-- $0: bleat and time could not be loaded<br> -->";
                }
            }
        }
    }
}
# Gathers all data require for display on specific users profile page
# Username, Full name, who they listen to, profile image, coordinates, suburb
# and bleats (formatted for output)
sub get_user_data
{
    my ($User_data, $user) = @_;
    $profile_img = "$user/profile.jpg";
    $profile_path = "~z5060961/$user/profile.jpg";
    $no_profile_img = "~z5060961/images/no_image.jpeg";
    # gather user personal information to be displayed
    # user's username
    $$User_data{'username'} = extract_username($user);
    # user's full name
    if (!($$User_data{'full_name'} = $USER_DATA{$$User_data{'username'}}{'full_name'})) {
        # handle no information case(s)
        $$User_data{'full_name'} = "Ha! You would like to know my name... wouldn't you?";
    }
    # who the user listens to
    my @listens = (sort keys %{ $USER_DATA{$$User_data{'username'}}{"listens"} });
    if (@listens) {
        # formating so that can latter be split and placed into 2 seperate
        # containers for allignment
        my $i = 1;
        foreach $entry (@listens) {
        		# turn user entries into button/links
        		$entry = get_link($entry, $entry, ($USER_INDEX{$entry}+1), "user_page");
            if (($i % 2) == 0) {
                $mod_listens[1] .= "$entry<br>";
            } else {
                $mod_listens[0] .= "$entry<br>"
            }
            $i++;
        }
        $$User_data{'listen_to'} = join ("&|!", @mod_listens);
    } else {
        # handle no information case(s)
        $$User_data{'listen_to'} = "no one";
    }
    # user's suburb
    if (!($$User_data{'suburb'} = $USER_DATA{$$User_data{'username'}}{"home_suburb"})) {
        # handle no information case(s)
        $$User_data{'suburb'} = "You're not getting my whereabouts!";
    }
    # user's image
    if (-e $profile_img) {
        $$User_data{'image'} = $profile_path;
    } else {
        # handle no information case(s)
        $$User_data{'image'} = $no_profile_img;
    }
    # user's coordinates
    if (exists($USER_DATA{$$User_data{'username'}}{"home_latitude"}) &&
        exists($USER_DATA{$$User_data{'username'}}{"home_longitude"})) {
        $$User_data{'coordinates'} = "$USER_DATA{$$User_data{'username'}}{'home_latitude'}, $USER_DATA{$$User_data{'username'}}{'home_longitude'}";
    } else {
        # handle no information case(s)
        $$User_data{'coordinates'} = "You're not getting my whereabouts!";
    }
    # gather user bleat information, load into new hash
    get_user_bleats(\%user_bleats, $$User_data{'username'});
    # add html formating and sort in reverse chronological order
    $$User_data{'bleats'} = format_bleats(\%user_bleats);
}

####################
# Helper Functions #
####################

# takes raw bleats and adds desired HTML formatting, including buttons/ links
# to user profiles
sub format_bleats
{
    my ($Bleats) = @_;
    my $username = param('username');
    # variables containing html formating for bleats
    my $pre = "<small class=\"text-success\"><strong>";
    my $mid = "</strong></small><br><br>";
    my $post = "<br><br><br>";
    # load to be printed bleats in chronological order includes html formating
    foreach my $time (sort keys %$Bleats) {
        foreach my $user (keys %{ $$Bleats{$time} }) {
            # add submit form passing hidden variables so that username is button/ link
            my $form_user = get_link($user, $user, ($USER_INDEX{$user}+1), "user_page");
            # Note: ths will be reversed
            push @print_bleats, $post;
            push @print_bleats, "$pre At $time $form_user bleated $mid $$Bleats{$time}{$user}";
        }
    }
    # we want bleats displayed in reverse chronological order
    return join('', reverse @print_bleats);
}


# returns a form that acts as a link to user home pages (primarily)
sub get_link
{
		my ($name, $user, $value, $param) = @_;
		my $username = param('username');
		# load form with given inputs to create desired link/ button
		my $button = "<form method=\"POST\" action=\"\">
		          <input type=\"hidden\" name=\"username\" value=\"$username\">
                  <input type=\"hidden\" name=\"authenticated\" value=\"1\">
                  <button type=\"submit\" class=\"btn btn-ghost btn-sm text-success\" name=\"$param\" value=\"$value\">$name</button>
                  </form>";
		return $button;
}

sub prevent_XSS
{
    # conforms to HTML use and will prefent injection attacks
    my $param = shift;
    $$param =~ s/&/&amp/g;
    $$param =~ s/</&lt/g;
    $$param =~ s/>/&gt/g;
    $$param =~ s/\"/&quot/g;
    $$param =~ s/\'/&#x27/g;
    $$param =~ s/\//&#x2F/g;
}

sub set_latest_bleat
{
    my ($Bleat_ref, $bleat_path) = @_;
    # each element is a bleat key
    @bleats = @$Bleat_ref;
    @bleats = sort @bleats;
    # while $latest is not the file latest_bleat, highest numerical value
    $i = '-1';
    $latest = $bleats[$i];
    while ($latest !~ /\d+/) {
        $i--;
        $latest = $bleats[$i];
    }
    # safety check as $latest should be largest value
    if ($latest !~ /\d+/) {
        print "<!--latest bleat key: $latest -->";
    }
    if ($latest < $bleats[0]) {
        $latest = $bleats[0];
    }
    # overide with new latest bleat number
    open(F, ">", "$bleat_path/latest_bleat") or die "$0: could not open $bleat_path/latest_bleat for writing";
    print F $latest; close F;
}

# clean line of leading/ trailing whitespace and prevent security threats
sub format_line
{
    my ($line) = @_;
    chomp $line;
    $line =~ s/^\s*|\s*$|\.\.|\\|//g;
    return $line;
}

# take user path and extract username
sub extract_username
{
    my ($user) = @_;
    $user =~ s/dataset\-.+\/users\///;
    return $user;
}

# take bleat path and extract bleat key
sub extract_bleat_keys
{
    my ($Keys) = @_;
    foreach $key (@$Keys) {
        $key =~ s/data.+bleats\///;
        push @new_keys, $key;
    }
    @$Keys = @new_keys;
}


###################
# Data processing #
###################

# Takes raw bleat input from user, cleans it, creates a file containing
# the bleat information, named the next sequential, unique bleat key and
# updates the relevant users bleat key list
sub process_new_bleat
{
    my $user_bleat = param('bleat');
    my $username = param('username');
    # clean input to prevent injection attacks
    $user_bleat = format_line($user_bleat);
    prevent_XSS(\$user_bleat);
    # establish bleat details
    my $time = time;
    my $lat = $USER_DATA{$username}{'latitude'};
    my $long = $USER_DATA{$username}{'longitude'};
    my $latest_path = "dataset-$dataset_size/bleats/latest_bleat";
    # get latest bleat number
    if (-e $latest_path) {
        open (F, "+<", "$latest_path") or die "<!--0: Could not open latest_bleat file-->";
        my $bleat_num = <F>;
        $bleat_num++;
        # update latest_bleat with new latest
        print F $bleat_num; close F;
        # add new bleat contents to be printed later
        push my @bleat_info, "username: $username\n";
        push @bleat_info, "latitude: $lat\n";
        push @bleat_info, "longitude: $long\n";
        push @bleat_info, "time: $time\n";
        push @bleat_info, "bleat: $user_bleat";
        # open file that will contain new bleat information
        $new_path = "dataset-$dataset_size/bleats/$bleat_num";
        open (F, ">", "$new_path") or die "<!-- $0: Could not open new bleat file: $bleat_num -->";
        print F @bleat_info; close F;
        $user_bleats_path = "dataset-$dataset_size/users/$username/bleats.txt";
        if (-e $user_bleats_path) {
            # append bleat number to users bleats
            open (F, ">>", "$user_bleats_path") or die "<!-- $0: Could not open $username bleat.txt file-->";
            print F "$bleat_num\n";
        } else {
            error_html();
        }
    } else {
        error_html();
    }
    # reprocess bleats
    process_users("dataset-$dataset_size/$username");
    process_user_bleats("dataset-$dataset_size/$username");
    process_bleats();
}

# Process each users file into hashes for later use
# A user index is also maintained to move to specific users profile pages
sub process_users
{
    my @users = @{$_[0]};
    $i = 0;
    foreach $user (@users) {
        my $username = extract_username($user);
         # load @user index information into hash
        $USER_INDEX{$username} = $i;
        # load user deatils into array
        $user_path = "$user/details.txt";
        open (F, "<", "$user_path") or die "<!-- $0: Could not open user details.txt: $user -->";
        @user_data = <F>; close F;
        #process user information into hash line by line
        foreach $line (@user_data) {
            $line = format_line($line);
            @s_line = split /: /,$line,2;
            # listens field case
            if ($s_line[0] =~ /listens/) {
                # users listened to stored as hash keys
                @listens_users = split / /,$s_line[1];
                foreach $listens (@listens_users) {
                    $USER_DATA{$username}{$s_line[0]}{$listens} = 1;
                }
            # all other information stored as hash values
            } else {
                $USER_DATA{$username}{$s_line[0]} = $s_line[1];
            }
        }
        # maintain for user index
        $i++;
    }
}

# Processes user bleat files into a hash for future reference
sub process_user_bleats
{
    my @user_paths = @{$_[0]};
    foreach my $user (@user_paths) {
        # get each users bleat key numbers
        open (F, "<", "$user/bleats.txt") or die "<!-- $0: Could not open $user bleats.txt<br>-->";
        @bleat_keys = <F>;  close F;
        my $username = extract_username($user);
        foreach $key (@bleat_keys) {
            $key = format_line($key);
            $USER_BLEATS{$username}{$key} = 1;
        }
    }
}

# Processes all user bleats into a hash
# Sets latest bleat
# Maintains mentioned users for each bleat key
# Adds buttons/links for user mentions
sub process_bleats
{
    my $bleats_path = "dataset-$dataset_size/bleats";
    @bleat_keys = glob("$bleats_path/*");
    # clean out path from glob
    extract_bleat_keys(\@bleat_keys);
    # find latest bleat key and store into a file for adding new bleats
    set_latest_bleat(\@bleat_keys, $bleats_path);
    foreach $key (@bleat_keys) {
        my @links;
        # open corresponding bleat files
        open (B, "<", "$bleats_path/$key") or die "$0: Could not open bleat file: $bleats_path/$key<br>";
        @bleat_data = <B>;  close B;
        # process bleat information line by line
        foreach $line (@bleat_data) {
            $line = format_line($line);
            @s_line = split /: /,$line,2;
            # extract tagged/ mentioned users
            if ($s_line[0] =~ /bleat/) {
                while ($s_line[1] =~ s/@([\w]+)/&tag&/) {
                    $MENTIONS{$key}{$1} = 1;
                    # add button link when a user is tagged
                    my $user_ref = $1;
            		push @links, get_link("\@$user_ref", $user_ref, ($USER_INDEX{$user_ref}+1), "user_page");
           		}

           		foreach $link (@links) {
           		    $s_line[1] =~ s/&tag&/$link/;
           		}
            }
            # add bleat data to hash
            $BLEAT_DATA{$key}{$s_line[0]} = $s_line[1];
        }
    }
}

main();
