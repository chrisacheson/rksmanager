-- Initial sqlite3 schema for the RKS database


-- All people that we have any dealings with. Note that id is the only column
-- guaranteed to be unique here. For people with ambiguous names you'll have to
-- use the other associated data to figure out if you have the right record,
-- unless you know their id.
create table people (
    id integer primary key
    , first_name_or_nickname text not null
    , pronouns text
    , notes text
);

-- Any other names that a person is known by. Mostly to make it easier to
-- search for them.
create table people_aliases (
    id integer primary key
    , person_id integer not null references people(id)
    , alias text not null
    , unique(person_id, alias)
);

-- Any email addresses associated with a person
create table people_email_addresses (
    id integer primary key
    , person_id integer not null references people(id)
    , email_address text not null unique
    , primary_email boolean_integer
        check(primary_email = 1) -- The address that we actually send email to
                                 -- should be marked as primary. Can only be 1
                                 -- or null.
    , unique(person_id, primary_email) -- Only one primary email per person
);

-- Any phone numbers associated with a person. Won't be used for most people,
-- but we want to enforce specific formatting for phone numbers otherwise they
-- become difficult to search for.
create table people_phone_numbers (
    id integer primary key
    , person_id integer not null references people(id)
    , country_code text not null -- Almost always 1 for USA
    , area_code text not null -- Usually 585 for Rochester
    , prefix text not null -- First 3 digits after area code
    , line_number text not null -- Last 4 digits
    , calls_okay boolean_integer
        check(calls_okay in (0, 1)) -- 1 if voice calls are okay, 0 if not, null
                                    -- if unknown
    , texts_okay boolean_integer
        check(texts_okay in (0, 1)) -- 1 if SMS messages are okay, 0 if not,
                                    -- null if unknown
    , unique(country_code, area_code, prefix, line_number)
);

-- Contact info types other than email addresses and phone numbers, such as
-- Fetlife or other social media usernames
create table other_contact_info_types (
    id integer primary key
    , name text not null unique
);

-- Any other contact info for a person besides email address or phone number
create table people_other_contact_info (
    id integer primary key
    , person_id integer not null references people(id)
    , other_contact_info_type_id integer not null
        references other_contact_info_types(id)
    , contact_info text not null
    , unique(other_contact_info_type_id, contact_info)
);

-- Membership types such as bronze, silver, gold, honorary, etc.
create table membership_types (
    id integer primary key
    , name text not null unique
);

-- Pricing options for each membership type, such as $20 per 1 month, $55 per 3
-- months, etc.
create table membership_type_pricing_options (
    id integer primary key
    , membership_type_id integer not null references membership_types(id)
    , length_months integer not null -- How many months the membership lasts per
                                     -- payment
    , price decimal_text not null
);

-- Any memberships that a person has or had
create table people_memberships (
    id integer primary key
    , person_id integer not null references people(id)
    , membership_type_id integer not null references membership_types(id)
    , begin_date date not null
    , end_date date -- If null, membership does not expire
);

-- Event types, such as munches, socials, workshops, and play parties
create table event_types (
    id integer primary key
    , name text not null unique
    , default_start_time timeofday_text
    , default_duration_minutes integer
);

-- Default door fee for an event type, per membership type
create table event_types_default_door_fees (
    id integer primary key
    , event_type_id integer not null references event_types(id)
    , membership_type_id integer not null references membership_types(id)
    , fee decimal_text not null
    , unique(event_type_id, membership_type_id)
);

-- Events
create table events (
    id integer primary key
    , event_type_id integer not null references event_types(id)
    , name text not null
    , begin_date_time timestamp not null
    , end_date_time timestamp not null
);

-- Door fee for a particular event, per membership type. Only needs to be used
-- if the door fees for an event are different than the defaults for that event
-- type.
create table events_door_fees (
    id integer primary key
    , event_id integer not null references events(id)
    , membership_type_id integer not null references membership_types(id)
    , fee decimal_text not null
    , unique(event_id, membership_type_id)
);

-- Payments that a person has made
create table people_payments (
    id integer primary key
    , person_id integer not null references people(id)
    , date_time timestamp not null
    , at_event_id references events(id) -- Event that this payment was received
                                        -- at
);

-- Individual charges that a payment covers
create table payments_items (
    id integer primary key
    , payment_id integer not null references people_payments(id)
    , amount decimal_text not null
);

-- Dues payments made on a membership
create table memberships_dues_payments (
    id integer primary key
    , membership_id integer not null references people_memberships(id)
    , payment_item_id integer not null references payments_items(id)
    , original_end_date date not null -- Date that the membership was set to
                                      -- expire on before the payment was made
    , new_end_date date not null -- New expiration date after applying the
                                 -- payment
);

-- Door fee payments made for an event
create table events_door_fee_payments (
    id integer primary key
    , event_id integer not null references events(id)
    , payment_item_id integer not null references payments_items(id)
);

-- Events that a person has attended
create table people_event_attendance (
    id integer primary key
    , person_id integer not null references people(id)
    , event_id integer not null references events(id)
    , guest_of_member_person_id integer
        references people(id) -- Member that they were the guest of, if any
);

-- The information sheets that we have first-time guests fill out
create table events_new_guest_info_sheets (
    id integer primary key
    , event_id integer not null references events(id)
    , person_id integer references people(id)
);

-- Information filled in on a new guest info sheet
create table new_guest_info_sheets_data (
    id integer primary key
    , info_sheet_id integer not null references events_new_guest_info_sheets(id)
    , field_name text not null
    , field_data text
    , field_behavior text -- Used by the software to mark this field for some
                          -- sort of special handling, like copying the data to
                          -- a particular field when creating a new person
                          -- record based on the info sheet
    , field_position integer not null -- Where this field should appear on the
                                      -- sheet (ascending order)
    , unique(info_sheet_id, field_name)
    , unique(info_sheet_id, field_behavior)
    , unique(info_sheet_id, field_position)
);

-- Default fields to include on new guest info sheets
create table new_guest_info_sheets_default_fields (
    id integer primary key
    , field_name text not null unique
    , field_behavior text unique
    , field_position integer not null unique
);

-- People who have been approved to become members, and the dates they were
-- approved on
create table people_membership_approval (
    id integer primary key
    , person_id integer not null references people(id)
    , approval_date date not null
);

-- People (usually guests) who have RSVPed to an event
create table people_event_rsvps (
    id integer primary key
    , person_id integer not null references people(id)
    , event_id integer not null references events(id)
    , rsvp_received_date date not null
    , guest_of_member_person_id integer
        references people(id) -- Member that they've RSVPed as the guest of, if
                              -- any
);

-- Types of legal documents that we keep on file from people, such as waivers
-- and NDAs
create table legal_document_types (
    id integer primary key
    , document_type text not null
);

-- Legal documents that we have on file from a person, such as waivers and NDAs
create table people_legal_documents (
    id integer primary key
    , person_id integer not null references people(id)
    , document_type_id integer not null references legal_document_types(id)
    , signed_date date not null
    , notes text
);

-- Incident reports submitted by a person
create table people_incident_reports (
    id integer primary key
    , reporter_person_id integer not null references people(id)
    , incident_date date not null
    , reported_date date not null
    , report text not null
);

-- People involved in an incident report
create table people_incident_reports_involvement (
    id integer primary key
    , report_id integer not null references people_incident_reports(id)
    , involved_person_id integer not null references people(id)
    , unique(report_id, involved_person_id)
);

-- Warnings issued to a person
create table people_warnings (
    id integer primary key
    , person_id integer not null references people(id)
    , warning_date date not null
    , notes text
);

-- Sanctions imposed on a person
create table people_sanctions (
    id integer primary key
    , person_id integer not null references people(id)
    , begin_date date not null
    , end_date date not null
    , notes text
);

-- Bans imposed on a person
create table people_bans (
    id integer primary key
    , person_id integer not null references people(id)
    , begin_date date not null
    , end_date date -- If null, ban is permanent
    , notes text
);
